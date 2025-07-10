import requests
import json
import logging
import time
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
import re
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Try to import outlines for structured outputs
try:
    import outlines
    from transformers import AutoTokenizer, AutoModelForCausalLM
    OUTLINES_AVAILABLE = True
    print("✅ Outlines available for guaranteed structured output")
except ImportError:
    OUTLINES_AVAILABLE = False
    print("❌ Outlines not available. Install with: pip install outlines transformers torch")

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading
_MODEL_CACHE = {}
_MODEL_LOCK = threading.Lock()

class RealEstateData(BaseModel):
    """Structured real estate property data model"""
    year_built: Optional[int] = Field(None, description="Year the property was built (e.g., 1990, 2018)")
    floor: Optional[str] = Field(None, description="Floor level (e.g., '3', 'EG', 'DG', '2. Stock')")
    condition: Optional[str] = Field(None, description="Property condition (e.g., 'renoviert', 'saniert', 'erstbezug')")
    heating: Optional[str] = Field(None, description="Heating type (e.g., 'Fernwärme', 'Gas', 'Fußbodenheizung')")
    parking: Optional[str] = Field(None, description="Parking availability (e.g., 'Tiefgarage', 'Stellplatz')")
    monatsrate: Optional[float] = Field(None, description="Monthly payment amount in EUR")
    own_funds: Optional[float] = Field(None, description="Required own funds/down payment in EUR")
    betriebskosten: Optional[float] = Field(None, description="Monthly operating costs in EUR")
    interest_rate: Optional[float] = Field(None, description="Interest rate for mortgage in percent")
    confidence: float = Field(0.0, description="Confidence score (0.0-1.0) for the extracted data")

class OutlinesAnalyzer:
    """
    Analyzer using Outlines for 100% guaranteed structured output
    """
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium", timeout_seconds: int = 10):
        self.model_name = model_name
        self.model = None
        self.timeout_seconds = timeout_seconds
        self._initialization_started = False
        self._initialization_complete = threading.Event()
        
        # Start lazy initialization in background
        self._start_lazy_initialization()
    
    def _start_lazy_initialization(self):
        """Start model initialization in background thread"""
        if self._initialization_started:
            return
            
        self._initialization_started = True
        
        def init_model():
            try:
                self._initialize_model()
                self._initialization_complete.set()
            except Exception as e:
                logger.error(f"❌ Background model initialization failed: {e}")
                self._initialization_complete.set()  # Set anyway to unblock
        
        # Start initialization in background thread
        init_thread = threading.Thread(target=init_model, daemon=True)
        init_thread.start()
    
    def _initialize_model(self):
        """Initialize the Outlines model with caching"""
        global _MODEL_CACHE, _MODEL_LOCK
        
        if not OUTLINES_AVAILABLE:
            logger.error("❌ Outlines not available")
            return
        
        with _MODEL_LOCK:
            # Check if model is already cached
            if self.model_name in _MODEL_CACHE:
                self.model = _MODEL_CACHE[self.model_name]
                logger.info(f"✅ Using cached Outlines model: {self.model_name}")
                return
            
            try:
                logger.info(f"🔧 Initializing Outlines with model: {self.model_name}")
                
                # Use ThreadPoolExecutor for timeout handling during model loading
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._load_model)
                    
                    try:
                        self.model = future.result(timeout=self.timeout_seconds)
                        
                        # Cache the model
                        _MODEL_CACHE[self.model_name] = self.model
                        logger.info("✅ Outlines model initialized successfully")
                        
                    except FutureTimeoutError:
                        logger.error(f"❌ Model initialization timed out after {self.timeout_seconds} seconds")
                        self.model = None
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize Outlines model: {e}")
                self.model = None
    
    def _load_model(self):
        """Load the model (called in thread with timeout)"""
        return outlines.models.transformers(self.model_name)
    
    def is_available(self) -> bool:
        """Check if analyzer is available"""
        if not OUTLINES_AVAILABLE:
            return False
        
        # Wait for initialization to complete (with shorter timeout)
        if not self._initialization_complete.wait(timeout=3):
            logger.warning("⚠️ Model initialization still in progress")
            return False
        
        return self.model is not None
    
    def analyze_listing(self, listing_data: Dict) -> Dict:
        """
        Analyze listing data and return structured output with timeout
        """
        if not self.is_available():
            logger.error("❌ Outlines analyzer not available")
            return self._create_default_result()
        
        try:
            # Prepare input text
            input_text = self._prepare_input_text(listing_data)
            
            # Create prompt for structured extraction
            prompt = f"""
            Analyze the following real estate listing data and extract structured information.
            
            LISTING DATA:
            {input_text}
            
            Extract the following information in JSON format:
            - year_built: Construction year (integer or null)
            - floor: Floor level (string or null)
            - condition: Property condition (string or null)
            - heating: Heating type (string or null)
            - parking: Parking availability (string or null)
            - monatsrate: Monthly payment amount (float or null)
            - own_funds: Required down payment (float or null)
            - betriebskosten: Monthly operating costs (float or null)
            - interest_rate: Interest rate percentage (float or null)
            - confidence: Confidence score 0.0-1.0 (float)
            
            Return only valid JSON with the exact field names above.
            """
            
            # Generate structured output with timeout
            logger.info("🧠 Generating structured output with Outlines...")
            
            # Use ThreadPoolExecutor for timeout handling
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._generate_with_outlines, prompt)
                
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    
                    # Parse the result - Outlines guarantees it matches our schema
                    if isinstance(result, str):
                        # Parse JSON string to dict
                        structured_data = json.loads(result)
                    else:
                        # Already a dict or Pydantic model
                        structured_data = result if isinstance(result, dict) else result.model_dump()
                    
                    # Count extracted fields
                    extracted_count = sum(1 for v in structured_data.values() 
                                        if v is not None and v != 0 and v != 0.0 and v != 0.0)
                    logger.info(f"✅ Outlines extracted {extracted_count} fields")
                    
                    return structured_data
                    
                except FutureTimeoutError:
                    logger.error(f"❌ Outlines analysis timed out after {self.timeout_seconds} seconds")
                    return self._create_default_result()
            
        except Exception as e:
            logger.error(f"❌ Outlines analysis failed: {e}")
            return self._create_default_result()
    
    def _generate_with_outlines(self, prompt: str):
        """Generate structured output with Outlines"""
        try:
            # Create a generator for structured output
            generator = outlines.generate.json(self.model, RealEstateData)
            return generator(prompt)
        except Exception as e:
            logger.error(f"❌ Outlines generation failed: {e}")
            raise

    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        """
        Analyze listing content and return enhanced data with structured extraction
        """
        try:
            # Enhance listing data with HTML content if available
            enhanced_listing_data = listing_data.copy()
            
            if raw_html:
                # Extract additional information from HTML
                soup = BeautifulSoup(raw_html, 'html.parser')
                
                # Extract text content for analysis
                text_content = soup.get_text(separator=' ', strip=True)
                if text_content:
                    enhanced_listing_data['html_content'] = text_content[:2000]  # Limit length
                
                # Try to extract additional fields from HTML
                additional_fields = self._extract_from_html(soup)
                enhanced_listing_data.update(additional_fields)
            
            # Get structured analysis with enhanced data
            analysis_result = self.analyze_listing(enhanced_listing_data)
            
            # Merge with original listing data
            enhanced_data = listing_data.copy()
            
            # Update with analysis results - only non-null values
            for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 
                         'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate']:
                if field in analysis_result and analysis_result[field] is not None:
                    enhanced_data[field] = analysis_result[field]
            
            # Add analysis metadata
            enhanced_data['structured_analysis'] = {
                'model': 'outlines',
                'model_name': self.model_name,
                'confidence': analysis_result.get('confidence', 0.0),
                'extracted_fields': [k for k, v in analysis_result.items() 
                                   if v is not None and k != 'confidence'],
                'timestamp': time.time()
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"❌ Error in analyze_listing_content: {e}")
            return listing_data
    
    def _extract_from_html(self, soup: BeautifulSoup) -> Dict:
        """Extract additional information from HTML content"""
        extracted = {}
        
        try:
            # Extract text content
            text = soup.get_text(separator=' ', strip=True)
            
            # Look for specific patterns in the text
            # Year built patterns
            year_patterns = [
                r'Baujahr[:\s]*(\d{4})',
                r'erbaut[:\s]*(\d{4})',
                r'Errichtung[:\s]*(\d{4})'
            ]
            for pattern in year_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        year = int(match.group(1))
                        if 1800 <= year <= 2025:
                            extracted['year_built'] = year
                            break
                    except ValueError:
                        continue
            
            # Floor patterns
            floor_patterns = [
                r'(\d+)\.?\s*Stock',
                r'(\d+)\.?\s*Etage',
                r'EG|Erdgeschoss',
                r'DG|Dachgeschoss'
            ]
            for pattern in floor_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if pattern in ['EG|Erdgeschoss', 'DG|Dachgeschoss']:
                        extracted['floor'] = match.group(0)
                    else:
                        extracted['floor'] = f"{match.group(1)}. Stock"
                    break
            
            # Condition patterns
            condition_patterns = [
                r'renoviert',
                r'saniert',
                r'erstbezug',
                r'neuwertig'
            ]
            for pattern in condition_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['condition'] = pattern
                    break
            
            # Heating patterns
            heating_patterns = [
                r'Fernwärme',
                r'Zentralheizung',
                r'Gas',
                r'Fußbodenheizung'
            ]
            for pattern in heating_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['heating'] = pattern
                    break
            
            # Parking patterns
            parking_patterns = [
                r'Tiefgarage',
                r'Stellplatz',
                r'Parkplatz'
            ]
            for pattern in parking_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['parking'] = pattern
                    break
            
            # Financial patterns
            monatsrate_patterns = [
                r'Monatsrate[:\s]*€?\s*([\d.,]+)',
                r'€?\s*([\d.,]+)\s*Monatsrate'
            ]
            for pattern in monatsrate_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 100 <= amount <= 10000:  # Reasonable range
                            extracted['monatsrate'] = amount
                            break
                    except ValueError:
                        continue
            
            eigenkapital_patterns = [
                r'Eigenkapital[:\s]*€?\s*([\d.,]+)',
                r'€?\s*([\d.,]+)\s*Eigenkapital'
            ]
            for pattern in eigenkapital_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 1000 <= amount <= 1000000:  # Reasonable range
                            extracted['own_funds'] = amount
                            break
                    except ValueError:
                        continue
            
            betriebskosten_patterns = [
                r'Betriebskosten[:\s]*€?\s*([\d.,]+)',
                r'Nebenkosten[:\s]*€?\s*([\d.,]+)'
            ]
            for pattern in betriebskosten_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 10 <= amount <= 1000:  # Reasonable range
                            extracted['betriebskosten'] = amount
                            break
                    except ValueError:
                        continue
            
        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
        
        return extracted

    def _prepare_input_text(self, listing_data: Dict) -> str:
        """Prepare input text from listing data"""
        parts = []
        
        # Add all available information
        for key, value in listing_data.items():
            if value is not None and value != "" and key not in ['url', 'sent_to_telegram', 'processed_at']:
                if key == 'description' and len(str(value)) > 1000:
                    # Truncate long descriptions
                    parts.append(f"{key}: {str(value)[:1000]}...")
                else:
                    parts.append(f"{key}: {value}")
        
        return "\n".join(parts)

    def _create_default_result(self) -> Dict:
        """Create default result when analysis fails"""
        return {
            "year_built": None,
            "floor": None,
            "condition": None,
            "heating": None,
            "parking": None,
            "monatsrate": None,
            "own_funds": None,
            "betriebskosten": None,
            "interest_rate": None,
            "confidence": 0.0
        }

# Add this new class after the OutlinesAnalyzer class

class LightweightAnalyzer:
    """
    Lightweight analyzer using regex patterns for fast extraction
    Fallback when Outlines is too slow or unavailable
    """
    
    def __init__(self):
        self.name = "lightweight-regex"
    
    def is_available(self) -> bool:
        """Always available - no model loading required"""
        return True
    
    def analyze_listing(self, listing_data: Dict) -> Dict:
        """
        Analyze listing data using regex patterns
        """
        try:
            # Extract text content for analysis
            text_content = self._extract_text_content(listing_data)
            
            # Use regex patterns to extract information
            extracted_data = self._extract_with_regex(text_content)
            
            # Calculate confidence based on how much we found
            extracted_count = sum(1 for v in extracted_data.values() if v is not None and v != 0 and v != 0.0)
            confidence = min(0.8, extracted_count / 9.0)  # Max 80% confidence for regex
            
            extracted_data['confidence'] = confidence
            
            logger.info(f"✅ Lightweight analyzer extracted {extracted_count} fields")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"❌ Lightweight analysis failed: {e}")
            return self._create_default_result()
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        """
        Analyze listing content with HTML enhancement
        """
        try:
            # Enhance listing data with HTML content
            enhanced_listing_data = listing_data.copy()
            
            if raw_html:
                soup = BeautifulSoup(raw_html, 'html.parser')
                text_content = soup.get_text(separator=' ', strip=True)
                if text_content:
                    enhanced_listing_data['html_content'] = text_content[:2000]
                
                # Extract additional fields from HTML
                additional_fields = self._extract_from_html(soup)
                enhanced_listing_data.update(additional_fields)
            
            # Get analysis results
            analysis_result = self.analyze_listing(enhanced_listing_data)
            
            # Merge with original listing data
            enhanced_data = listing_data.copy()
            
            # Update with analysis results - only non-null values
            for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 
                         'monatsrate', 'own_funds', 'betriebskosten', 'interest_rate']:
                if field in analysis_result and analysis_result[field] is not None:
                    enhanced_data[field] = analysis_result[field]
            
            # Add analysis metadata
            enhanced_data['structured_analysis'] = {
                'model': 'lightweight-regex',
                'confidence': analysis_result.get('confidence', 0.0),
                'extracted_fields': [k for k, v in analysis_result.items() 
                                   if v is not None and k != 'confidence'],
                'timestamp': time.time()
            }
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"❌ Error in lightweight analyze_listing_content: {e}")
            return listing_data
    
    def _extract_text_content(self, listing_data: Dict) -> str:
        """Extract text content from listing data"""
        parts = []
        
        for key, value in listing_data.items():
            if value is not None and value != "" and key not in ['url', 'sent_to_telegram', 'processed_at']:
                if key == 'description' and len(str(value)) > 1000:
                    parts.append(f"{key}: {str(value)[:1000]}...")
                else:
                    parts.append(f"{key}: {value}")
        
        return "\n".join(parts)
    
    def _extract_with_regex(self, text: str) -> Dict:
        """Extract information using regex patterns"""
        extracted = {
            "year_built": None,
            "floor": None,
            "condition": None,
            "heating": None,
            "parking": None,
            "monatsrate": None,
            "own_funds": None,
            "betriebskosten": None,
            "interest_rate": None,
            "confidence": 0.0
        }
        
        try:
            # Year built patterns
            year_patterns = [
                r'Baujahr[:\s]*(\d{4})',
                r'erbaut[:\s]*(\d{4})',
                r'(\d{4})\s*erbaut',
                r'Jahr[:\s]*(\d{4})'
            ]
            for pattern in year_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    year = int(match.group(1))
                    if 1800 <= year <= 2025:
                        extracted['year_built'] = year
                        break
            
            # Floor patterns
            floor_patterns = [
                r'(\d+)\.?\s*Stock',
                r'(\d+)\.?\s*Etage',
                r'Stock[:\s]*(\d+)',
                r'Etage[:\s]*(\d+)'
            ]
            for pattern in floor_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    floor_num = match.group(1)
                    extracted['floor'] = f"{floor_num}. Stock"
                    break
            
            # Condition patterns
            condition_patterns = [
                r'renoviert',
                r'saniert',
                r'erstbezug',
                r'neuwertig',
                r'neu'
            ]
            for pattern in condition_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['condition'] = pattern
                    break
            
            # Heating patterns
            heating_patterns = [
                r'Fernwärme',
                r'Zentralheizung',
                r'Gas',
                r'Fußbodenheizung',
                r'Heizung'
            ]
            for pattern in heating_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['heating'] = pattern
                    break
            
            # Parking patterns
            parking_patterns = [
                r'Tiefgarage',
                r'Stellplatz',
                r'Parkplatz',
                r'Garage'
            ]
            for pattern in parking_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    extracted['parking'] = pattern
                    break
            
            # Financial patterns
            monatsrate_patterns = [
                r'Monatsrate[:\s]*€?\s*([\d.,]+)',
                r'€?\s*([\d.,]+)\s*Monatsrate',
                r'Rate[:\s]*€?\s*([\d.,]+)'
            ]
            for pattern in monatsrate_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 100 <= amount <= 10000:  # Reasonable range
                            extracted['monatsrate'] = amount
                            break
                    except ValueError:
                        continue
            
            eigenkapital_patterns = [
                r'Eigenkapital[:\s]*€?\s*([\d.,]+)',
                r'€?\s*([\d.,]+)\s*Eigenkapital',
                r'Eigenmittel[:\s]*€?\s*([\d.,]+)'
            ]
            for pattern in eigenkapital_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 1000 <= amount <= 1000000:  # Reasonable range
                            extracted['own_funds'] = amount
                            break
                    except ValueError:
                        continue
            
            betriebskosten_patterns = [
                r'Betriebskosten[:\s]*€?\s*([\d.,]+)',
                r'Nebenkosten[:\s]*€?\s*([\d.,]+)',
                r'BK[:\s]*€?\s*([\d.,]+)'
            ]
            for pattern in betriebskosten_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        amount = float(match.group(1).replace('.', '').replace(',', '.'))
                        if 10 <= amount <= 1000:  # Reasonable range
                            extracted['betriebskosten'] = amount
                            break
                    except ValueError:
                        continue
            
            # Interest rate patterns
            interest_patterns = [
                r'Zinssatz[:\s]*([\d.,]+)\s*%',
                r'([\d.,]+)\s*%\s*Zinssatz',
                r'Zins[:\s]*([\d.,]+)\s*%'
            ]
            for pattern in interest_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        rate = float(match.group(1).replace(',', '.'))
                        if 0.1 <= rate <= 20:  # Reasonable range
                            extracted['interest_rate'] = rate
                            break
                    except ValueError:
                        continue
            
        except Exception as e:
            logger.error(f"Error in regex extraction: {e}")
        
        return extracted
    
    def _extract_from_html(self, soup: BeautifulSoup) -> Dict:
        """Extract additional information from HTML content"""
        extracted = {}
        
        try:
            # Extract text content
            text = soup.get_text(separator=' ', strip=True)
            
            # Use the same regex patterns as above
            regex_result = self._extract_with_regex(text)
            
            # Only add non-null values
            for key, value in regex_result.items():
                if value is not None and key != 'confidence':
                    extracted[key] = value
            
        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
        
        return extracted
    
    def _create_default_result(self) -> Dict:
        """Create default result when analysis fails"""
        return {
            "year_built": None,
            "floor": None,
            "condition": None,
            "heating": None,
            "parking": None,
            "monatsrate": None,
            "own_funds": None,
            "betriebskosten": None,
            "interest_rate": None,
            "confidence": 0.0
        }

# Main StructuredAnalyzer class - simplified and optimized with aggressive fallback
class StructuredAnalyzer:
    """
    Structured analyzer using Outlines with aggressive lightweight fallback
    """
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium", outlines_wait_timeout: float = 0.5, **kwargs):
        # Try Outlines first, fallback to lightweight
        self.outlines_analyzer = OutlinesAnalyzer(model_name=model_name)
        self.lightweight_analyzer = LightweightAnalyzer()
        self.outlines_wait_timeout = outlines_wait_timeout
        
    def is_available(self) -> bool:
        """Check if any analyzer is available"""
        return self.outlines_analyzer.is_available() or self.lightweight_analyzer.is_available()
    
    def _wait_for_outlines(self, timeout: float) -> bool:
        """Wait up to timeout seconds for Outlines to become available"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.outlines_analyzer.is_available():
                return True
            time.sleep(0.1)
        return False
    
    def _safe_outlines_analysis(self, method_name: str, *args, **kwargs):
        """Safely call Outlines analysis with timeout"""
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                if method_name == 'analyze_listing_content':
                    future = executor.submit(self.outlines_analyzer.analyze_listing_content, *args, **kwargs)
                else:
                    future = executor.submit(self.outlines_analyzer.analyze_listing, *args, **kwargs)
                
                return future.result(timeout=3.0)  # 3 second timeout for analysis
                
        except FutureTimeoutError:
            logger.warning(f"⚠️ Outlines {method_name} timed out after 3s, falling back to lightweight")
            raise TimeoutError(f"Outlines {method_name} timed out")
        except Exception as e:
            logger.warning(f"⚠️ Outlines {method_name} failed: {e}, falling back to lightweight")
            raise
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        """Analyze listing content with lightweight analyzer only for speed"""
        # Skip Outlines entirely and use lightweight analyzer for maximum speed
        logger.info("⚡ Using lightweight analyzer for speed...")
        return self.lightweight_analyzer.analyze_listing_content(listing_data, raw_html)
    
    def analyze_listing(self, listing_data: Dict) -> Dict:
        """Analyze listing with lightweight analyzer only for speed"""
        # Skip Outlines entirely and use lightweight analyzer for maximum speed
        logger.info("⚡ Using lightweight analyzer for speed...")
        return self.lightweight_analyzer.analyze_listing(listing_data)
    
    def _create_default_result(self) -> Dict:
        """Create default result when analysis fails"""
        return {
            "year_built": None,
            "floor": None,
            "condition": None,
            "heating": None,
            "parking": None,
            "monatsrate": None,
            "own_funds": None,
            "betriebskosten": None,
            "interest_rate": None,
            "confidence": 0.0
        }

# Backward compatibility - simplified
class OllamaAnalyzer:
    """
    Backward compatibility wrapper - redirects to OutlinesAnalyzer
    """
    def __init__(self, model_name: str = "microsoft/DialoGPT-small", **kwargs):
        print("⚠️  OllamaAnalyzer is deprecated. Use OutlinesAnalyzer for guaranteed structured output.")
        self.outlines_analyzer = OutlinesAnalyzer(model_name=model_name)
        
    def is_available(self) -> bool:
        return self.outlines_analyzer.is_available()
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        return self.outlines_analyzer.analyze_listing_content(listing_data, raw_html)
    
    def analyze_listing(self, listing_data: Dict) -> Dict:
        return self.outlines_analyzer.analyze_listing(listing_data)

# Utility functions - simplified
def fetch_url_with_retries(url, max_retries=3, delay=2):
    """Fetch URL with retries"""
    for attempt in range(1, max_retries+1):
        try:
            logger.debug(f"Fetching URL (attempt {attempt}): {url}")
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp
        except Exception as e:
            logger.error(f"Error fetching {url} (attempt {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(delay * attempt)
            else:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts.")
    return None

def extract_clean_text(html):
    """Extract clean text from HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return text 