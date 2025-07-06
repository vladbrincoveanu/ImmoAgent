import requests
import json
from typing import Dict, Optional, List
import logging

class OllamaAnalyzer:
    def __init__(self, model_name: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        
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
        """Analyze listing content using Ollama LLM to extract missing information"""
        if not self.is_available():
            logging.warning("Ollama not available, skipping content analysis")
            return listing_data
        
        try:
            # Extract text content from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_html, 'html.parser')
            
            # Get main content areas
            content_selectors = [
                '.description',
                '.listing-description', 
                '.property-details',
                '.additional-info',
                '.details',
                '[data-testid="description"]',
                '.search-result-entry__description'
            ]
            
            content_text = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    content_text += elem.get_text(separator=' ', strip=True) + "\n"
            
            # If no specific content found, get all text
            if not content_text.strip():
                content_text = soup.get_text(separator=' ', strip=True)
            
            # Limit content length to avoid token limits
            content_text = content_text[:4000]
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(listing_data, content_text)
            
            # Call Ollama
            response = self._call_ollama(prompt)
            
            if response:
                # Parse the response and update listing data
                updated_data = self._parse_analysis_response(response, listing_data)
                return updated_data
            
        except Exception as e:
            logging.error(f"Error analyzing listing content: {e}")
        
        return listing_data
    
    def _create_analysis_prompt(self, listing_data: Dict, content_text: str) -> str:
        """Create a prompt for analyzing the listing content"""
        
        prompt = f"""
You are a real estate data analyst. Analyze the following property listing content and extract missing information.

CURRENT LISTING DATA:
{json.dumps(listing_data, indent=2, ensure_ascii=False)}

PROPERTY DESCRIPTION:
{content_text}

TASK: Analyze the content and provide the following information in JSON format:

1. **Missing Information**: Identify what key information is missing from the current data
2. **Extracted Data**: Extract any missing information from the content
3. **Content Quality**: Assess the quality and completeness of the listing description
4. **Red Flags**: Identify any potential issues or concerns mentioned
5. **Additional Details**: Extract any additional useful information

RESPONSE FORMAT (JSON):
{{
    "missing_information": ["list of missing key data points"],
    "extracted_data": {{
        "year_built": "extracted year or null",
        "rooms": "extracted room count or null", 
        "floor": "extracted floor info or null",
        "condition": "extracted condition or null",
        "heating": "extracted heating type or null",
        "parking": "extracted parking info or null",
        "address": "extracted address or null",
        "monatsrate": "extracted monthly rate or null",
        "special_conditions": "any special conditions mentioned",
        "amenities": ["list of amenities mentioned"],
        "renovation_info": "any renovation information",
        "energy_info": "energy efficiency information"
    }},
    "content_quality": {{
        "completeness_score": "1-10 score",
        "detail_level": "low/medium/high",
        "missing_critical_info": ["list of critical missing info"]
    }},
    "red_flags": ["list of potential issues"],
    "additional_details": "any other relevant information"
}}

Analyze carefully and provide accurate, structured information.
"""
        return prompt
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "max_tokens": 2000
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except Exception as e:
            logging.error(f"Error calling Ollama: {e}")
            return None
    
    def _parse_analysis_response(self, response: str, original_data: Dict) -> Dict:
        """Parse Ollama response and update listing data"""
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)
                
                # Update original data with extracted information
                updated_data = original_data.copy()
                
                extracted = analysis.get('extracted_data', {})
                
                # Update only if current value is None/empty and we have new data
                for key, value in extracted.items():
                    if value and value != "null" and value != "None":
                        if key == "year_built" and isinstance(value, str):
                            try:
                                updated_data[key] = int(value)
                            except:
                                pass
                        elif key == "rooms" and isinstance(value, str):
                            try:
                                updated_data[key] = int(value)
                            except:
                                pass
                        elif key == "monatsrate" and isinstance(value, str):
                            try:
                                # Extract number from string like "€1,200" or "1200"
                                import re
                                num_match = re.search(r'[\d,]+', value.replace('€', '').replace(',', ''))
                                if num_match:
                                    updated_data[key] = float(num_match.group())
                            except:
                                pass
                        else:
                            updated_data[key] = value
                
                # Add analysis metadata
                updated_data['content_analysis'] = {
                    'quality_score': analysis.get('content_quality', {}).get('completeness_score', 'N/A'),
                    'missing_info': analysis.get('missing_information', []),
                    'red_flags': analysis.get('red_flags', []),
                    'additional_details': analysis.get('additional_details', '')
                }
                
                logging.info(f"Content analysis completed. Quality score: {updated_data['content_analysis']['quality_score']}")
                return updated_data
                
        except Exception as e:
            logging.error(f"Error parsing analysis response: {e}")
        
        return original_data
    
    def batch_analyze_listings(self, listings: List[Dict], raw_htmls: List[str]) -> List[Dict]:
        """Analyze multiple listings in batch"""
        if not self.is_available():
            logging.warning("Ollama not available, returning original listings")
            return listings
        
        analyzed_listings = []
        for i, (listing, html) in enumerate(zip(listings, raw_htmls)):
            logging.info(f"Analyzing listing {i+1}/{len(listings)}")
            analyzed_listing = self.analyze_listing_content(listing, html)
            analyzed_listings.append(analyzed_listing)
        
        return analyzed_listings 