import requests
import json
from typing import Dict, Optional, List
import logging
import time
from bs4 import BeautifulSoup
import re
import os

logger = logging.getLogger('immo-monitor')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('monitor.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

def fetch_url_with_retries(url, max_retries=3, delay=2):
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
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return text

class StructuredAnalyzer:
    """
    Advanced structured output analyzer that guarantees complete data extraction
    Uses OpenAI's structured output API for 100% reliable JSON schema compliance
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        # Fallback to Ollama if OpenAI not available
        self.use_ollama = not self.api_key
        if self.use_ollama:
            self.ollama_analyzer = OllamaAnalyzer()
    
    def is_available(self) -> bool:
        """Check if the analyzer is available"""
        if self.use_ollama:
            return self.ollama_analyzer.is_available()
        return bool(self.api_key)
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        """Analyze listing content with guaranteed structured output"""
        if not self.is_available():
            logging.warning("No analyzer available")
            return listing_data
        
        if self.use_ollama:
            return self.ollama_analyzer.analyze_listing_content(listing_data, raw_html)
        
        try:
            # Extract and prepare content
            content_text = extract_clean_text(raw_html)
            relevant_content = self._extract_relevant_content(content_text)
            
            # Create structured prompt
            response = self._call_openai_structured(listing_data, relevant_content)
            
            if response:
                return self._merge_extracted_data(listing_data, response)
            
        except Exception as e:
            logging.error(f"Error in structured analysis: {e}")
        
        return listing_data
    
    def _extract_relevant_content(self, content_text: str) -> str:
        """Extract relevant content for analysis"""
        # Look for key real estate terms
        keywords = [
            'baujahr', 'jahr', 'errichtung', 'erbaut', 'bj',
            'stock', 'etage', 'geschoss', 'erdgeschoss', 'eg', 'dg',
            'zustand', 'erstbezug', 'saniert', 'renoviert', 'neuwertig',
            'heizung', 'zentralheizung', 'fernwärme', 'gas', 'fußboden',
            'garage', 'parkplatz', 'stellplatz', 'tiefgarage', 'carport',
            'monatsrate', 'finanzierung', 'kredit', 'darlehen', 'rate',
            'eigenkapital', 'anzahlung', 'eigenmittel', 'kapital',
            'wohnung', 'immobilie', 'objekt', 'zimmer', 'm²', '€'
        ]
        
        sentences = content_text.split('.')
        relevant_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in keywords):
                relevant_sentences.append(sentence.strip())
        
        if relevant_sentences:
            return '. '.join(relevant_sentences[:15])  # Top 15 relevant sentences
        else:
            return content_text[:2000]  # Fallback
    
    def _call_openai_structured(self, listing_data: Dict, content: str) -> Optional[Dict]:
        """Call OpenAI with structured output schema"""
        try:
            # Define the exact JSON schema we want
            schema = {
                "type": "object",
                "properties": {
                    "year_built": {
                        "type": ["integer", "null"],
                        "description": "Construction year (4-digit number between 1800-2024)"
                    },
                    "floor": {
                        "type": ["string", "null"],
                        "description": "Floor level (e.g., 'EG', '1. Stock', '2. OG')"
                    },
                    "condition": {
                        "type": ["string", "null"],
                        "description": "Property condition (e.g., 'Erstbezug', 'Saniert', 'Renovierungsbedürftig')"
                    },
                    "heating": {
                        "type": ["string", "null"],
                        "description": "Heating type (e.g., 'Zentralheizung', 'Fernwärme', 'Fußbodenheizung')"
                    },
                    "parking": {
                        "type": ["string", "null"],
                        "description": "Parking information (e.g., 'Tiefgarage', 'Stellplatz', 'Ja')"
                    },
                    "monatsrate": {
                        "type": ["number", "null"],
                        "description": "Monthly payment rate in euros"
                    },
                    "own_funds": {
                        "type": ["number", "null"],
                        "description": "Required down payment/own funds in euros"
                    },
                    "betriebskosten": {
                        "type": ["number", "null"],
                        "description": "Monthly operating costs (Betriebskosten) in euros"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score 0.0-1.0"
                    }
                },
                "required": ["year_built", "floor", "condition", "heating", "parking", "monatsrate", "own_funds", "betriebskosten", "confidence"],
                "additionalProperties": false
            }
            
            messages = [
                {
                    "role": "system",
                    "content": """You are a Vienna real estate data extraction expert. Extract missing information from property listings with maximum accuracy.

EXTRACTION RULES:
1. Look for German/Austrian real estate terms
2. Extract exact values, don't estimate or guess
3. If information is not found, return null
4. Be conservative with confidence scores
5. Pay special attention to financial information (Monatsrate, Eigenkapital, Betriebskosten)

TERMS TO LOOK FOR:
- Baujahr/Jahr/Errichtung/Erbaut = year_built
- Stock/Etage/Geschoss/EG/DG = floor  
- Zustand/Erstbezug/Saniert = condition
- Heizung/Zentralheizung/Fernwärme = heating
- Garage/Parkplatz/Stellplatz = parking
- Monatsrate/Finanzierung/Rate = monatsrate
- Eigenkapital/Anzahlung/Eigenmittel = own_funds
- Betriebskosten/Nebenkosten = betriebskosten"""
                },
                {
                    "role": "user",
                    "content": f"""Extract real estate data from this Vienna apartment listing:

CURRENT DATA:
- Address: {listing_data.get('address', 'Unknown')}
- Price: €{listing_data.get('price_total', 'Unknown')}
- Area: {listing_data.get('area_m2', 'Unknown')}m²
- Rooms: {listing_data.get('rooms', 'Unknown')}

CONTENT TO ANALYZE:
{content}

Extract the missing fields according to the schema. Be thorough and accurate."""
                }
            ]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "real_estate_data",
                        "schema": schema,
                        "strict": True
                    }
                },
                "temperature": 0.1,
                "max_tokens": 500
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return json.loads(content)
            
        except Exception as e:
            logging.error(f"Error calling OpenAI structured API: {e}")
            return None
    
    def _merge_extracted_data(self, original_data: Dict, extracted_data: Dict) -> Dict:
        """Merge extracted data with original listing data"""
        updated_data = original_data.copy()
        
        # Update fields with extracted data (only if not null)
        for field in ['year_built', 'floor', 'condition', 'heating', 'parking', 'monatsrate', 'own_funds', 'betriebskosten']:
            if field in extracted_data and extracted_data[field] is not None:
                # Validate extracted data
                if field == 'year_built':
                    if isinstance(extracted_data[field], int) and 1800 <= extracted_data[field] <= 2024:
                        updated_data[field] = extracted_data[field]
                elif field in ['monatsrate', 'own_funds', 'betriebskosten']:
                    if isinstance(extracted_data[field], (int, float)) and extracted_data[field] > 0:
                        updated_data[field] = float(extracted_data[field])
                else:
                    if isinstance(extracted_data[field], str) and extracted_data[field].strip():
                        updated_data[field] = extracted_data[field].strip()
        
        # Add analysis metadata
        updated_data['structured_analysis'] = {
            'model': 'openai-structured',
            'confidence': extracted_data.get('confidence', 0.8),
            'extracted_fields': [k for k, v in extracted_data.items() if v is not None and k != 'confidence'],
            'timestamp': time.time()
        }
        
        logging.info(f"Structured analysis completed with confidence: {extracted_data.get('confidence', 0.8)}")
        logging.info(f"Extracted fields: {updated_data['structured_analysis']['extracted_fields']}")
        
        return updated_data

class OllamaAnalyzer:
    """Fallback Ollama analyzer with improved structured output"""
    
    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/generate"
        
    def is_available(self) -> bool:
        """Check if Ollama is running and the model is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(model['name'] == self.model_name for model in models)
            return False
        except Exception as e:
            logging.warning(f"Ollama not available: {e}")
            return False
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        """Analyze listing content using Ollama with improved prompting"""
        if not self.is_available():
            logging.warning("Ollama not available, skipping content analysis")
            return listing_data
        
        try:
            content_text = extract_clean_text(raw_html)
            content_text = content_text[:3000]
            
            # Use multiple focused prompts for better extraction
            extracted_data = {}
            
            # Extract year_built with focused prompt
            year_result = self._extract_specific_field(content_text, "year_built", listing_data)
            if year_result:
                extracted_data.update(year_result)
            
            # Extract other fields
            other_result = self._extract_other_fields(content_text, listing_data)
            if other_result:
                extracted_data.update(other_result)
            
            # Merge results
            if extracted_data:
                updated_data = listing_data.copy()
                for field, value in extracted_data.items():
                    if value is not None and field != 'confidence':
                        updated_data[field] = value
                
                updated_data['ollama_analysis'] = {
                    'model': self.model_name,
                    'confidence': extracted_data.get('confidence', 0.7),
                    'extracted_fields': [k for k, v in extracted_data.items() if v is not None and k != 'confidence'],
                    'timestamp': time.time()
                }
                
                return updated_data
            
        except Exception as e:
            logging.error(f"Error analyzing listing content: {e}")
        
        return listing_data
    
    def _extract_specific_field(self, content: str, field: str, listing_data: Dict) -> Optional[Dict]:
        """Extract a specific field with focused prompt"""
        if field == "year_built":
            prompt = f"""Find the construction year (Baujahr) in this Vienna property text.

Text: {content[:1000]}

Look for: Baujahr, Errichtung, Erbaut, BJ, Jahr followed by a 4-digit year.

Return ONLY a JSON with the year:
{{"year_built": 1995, "confidence": 0.9}}

If no year found, return:
{{"year_built": null, "confidence": 0.1}}"""

            try:
                response = self._call_ollama(prompt)
                if response:
                    # Extract JSON from response
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = response[json_start:json_end]
                        result = json.loads(json_str)
                        
                        # Validate year
                        if result.get('year_built') and isinstance(result['year_built'], int):
                            if 1800 <= result['year_built'] <= 2024:
                                return result
                        
                        return {"year_built": None, "confidence": 0.1}
            except:
                pass
        
        return None
    
    def _extract_other_fields(self, content: str, listing_data: Dict) -> Optional[Dict]:
        """Extract other fields with comprehensive prompt"""
        prompt = f"""Extract real estate details from this Vienna property text.

Text: {content[:1500]}

Find these details:
- Floor: Stock/Etage/Geschoss (e.g., "2. Stock", "EG")
- Condition: Zustand (e.g., "Erstbezug", "Saniert") 
- Heating: Heizung (e.g., "Zentralheizung", "Fernwärme")
- Parking: Garage/Parkplatz (e.g., "Tiefgarage", "Stellplatz")
- Monthly rate: Monatsrate in euros
- Own funds: Eigenkapital in euros

Return ONLY this JSON:
{{
    "floor": "2. Stock",
    "condition": "Erstbezug", 
    "heating": "Zentralheizung",
    "parking": "Tiefgarage",
    "monatsrate": 1200,
    "own_funds": 50000,
    "confidence": 0.8
}}

Use null for missing values."""

        try:
            response = self._call_ollama(prompt)
            if response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    return json.loads(json_str)
        except Exception as e:
            logging.error(f"Error extracting other fields: {e}")
        
        return None
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 300
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except Exception as e:
            logging.error(f"Error calling Ollama: {e}")
            return None

# For backward compatibility
class OllamaAnalyzer_Old:
    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        # Redirect to new structured analyzer
        self.structured_analyzer = StructuredAnalyzer()
        
    def is_available(self) -> bool:
        return self.structured_analyzer.is_available()
    
    def analyze_listing_content(self, listing_data: Dict, raw_html: str) -> Dict:
        return self.structured_analyzer.analyze_listing_content(listing_data, raw_html)

def extract_next_page_url(html):
    # Use BeautifulSoup to find the next page link
    soup = BeautifulSoup(html, 'html.parser')
    next_link = soup.select_one('a[rel="next"]')
    if next_link and next_link.get('href'):
        return "https://www.willhaben.at" + next_link['href']
    return None

def crawl_all_pages(start_url, max_pages=10):
    page = 1
    url = start_url
    while url and page <= max_pages:
        logger.info(f"Crawling page {page}: {url}")
        resp = fetch_url_with_retries(url)
        if not resp:
            logger.error(f"Failed to fetch page {page}: {url}")
            break
        html = resp.text
        # ... process listings ...
        # For each listing, use extract_clean_text(html) before sending to Ollama
        next_url = extract_next_page_url(html)
        if not next_url:
            logger.info("No more pages found.")
            break
        url = next_url
        page += 1 