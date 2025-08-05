# utils/llm_client.py
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv

import os

load_dotenv()

class GeminiClient:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        
        
        # Create a simple agent for LLM calls
        self.agent = Agent(
            name="NutritionAnalyzer",
            model=Gemini(
                id=os.environ['DEFAULT_MODEL'],
                vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
                project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
                location=os.environ['GOOGLE_CLOUD_LOCATION'],
                api_key=os.environ.get('GOOGLE_API_KEY')
            ),
            description="Analyzes nutrition and generates meal plans",
            show_tool_calls=False,
            markdown=False
        )
    
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Gemini through agno Agent"""
        try:
            response = self.agent.run(prompt)
            if response and hasattr(response, 'content') and response.content:
                return response.content.strip()
            elif isinstance(response, str):
                return response.strip()
            else:
                return "Unable to generate response. Please try again."
        except Exception as e:
            print(f"LLM API Error: {str(e)}")
            return f"Error generating response: {str(e)}"
    
    def categorize_food_nutrients(self, meal_description: str) -> Dict[str, float]:
        """Categorize food into macronutrients"""
        prompt = f"""
        Analyze the following meal description and estimate the macronutrients.
        Provide your response in this exact JSON format:
        {{
            "carbs": <grams>,
            "protein": <grams>,
            "fat": <grams>,
            "calories": <total_calories>
        }}
        
        Meal: {meal_description}
        
        Be realistic with portions and provide reasonable estimates.
        Only respond with the JSON, no other text.
        """
        
        response = self.generate_response(prompt)
        try:
            # Extract JSON from response
            import json
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                parsed = json.loads(json_str)
                # Validate required fields
                required_fields = ['carbs', 'protein', 'fat', 'calories']
                if all(field in parsed for field in required_fields):
                    return parsed
                else:
                    print(f"Missing required fields in nutrition response: {parsed}")
                    return self._fallback_nutrition()
            else:
                print(f"No valid JSON found in nutrition response: {response}")
                return self._fallback_nutrition()
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in nutrition analysis: {e}")
            return self._fallback_nutrition()
        except Exception as e:
            print(f"Unexpected error in nutrition analysis: {e}")
            return self._fallback_nutrition()
    
    def generate_meal_plan(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized meal plan"""
        conditions = ", ".join(user_context['medical_conditions'])
        
        prompt = f"""
        Create a personalized daily meal plan for a user with the following profile:
        
        - Dietary Category: {user_context['dietary_category']}
        - Medical Conditions: {conditions}
        - Recent Average Mood: {user_context.get('recent_mood_avg', 'N/A')}/10
        - Recent Average CGM: {user_context.get('recent_cgm_avg', 'N/A')} mg/dL
        
        Guidelines:
        - If diabetic: Focus on low glycemic index foods, limit simple carbs
        - If hypertensive: Reduce sodium, emphasize potassium-rich foods
        - If vegetarian/vegan: Ensure adequate protein sources
        - Consider mood: If low mood, include mood-boosting foods
        
        Provide response in this exact JSON format:
        {{
            "breakfast": "Detailed breakfast description with approximate portions",
            "lunch": "Detailed lunch description with approximate portions",
            "dinner": "Detailed dinner description with approximate portions",
            "total_calories": <estimated_total>,
            "total_carbs": <estimated_total_grams>,
            "total_protein": <estimated_total_grams>,
            "total_fat": <estimated_total_grams>,
            "notes": "Any special considerations or tips"
        }}
        
        Only respond with the JSON, no other text.
        """
        
        response = self.generate_response(prompt)
        try:
            import json
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                parsed = json.loads(json_str)
                # Validate required fields for meal plan
                required_fields = ['breakfast', 'lunch', 'dinner']
                if all(field in parsed for field in required_fields):
                    return parsed
                else:
                    print(f"Missing required fields in meal plan response: {parsed}")
                    return self._fallback_meal_plan(user_context)
            else:
                print(f"No valid JSON found in meal plan response: {response}")
                return self._fallback_meal_plan(user_context)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in meal planning: {e}")
            return self._fallback_meal_plan(user_context)
        except Exception as e:
            print(f"Unexpected error in meal planning: {e}")
            return self._fallback_meal_plan(user_context)
    
    def _fallback_meal_plan(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback meal plan if LLM fails"""
        dietary = user_context['dietary_category'].lower()
        
        if 'vegan' in dietary:
            return {
                "breakfast": "Oatmeal with berries and almond butter (1 cup oats, 1/2 cup berries, 2 tbsp almond butter)",
                "lunch": "Quinoa buddha bowl with chickpeas and vegetables (1 cup quinoa, 1/2 cup chickpeas, mixed vegetables)",
                "dinner": "Lentil curry with brown rice (1 cup lentils, 1 cup brown rice, spices)",
                "total_calories": 1800,
                "total_carbs": 250,
                "total_protein": 75,
                "total_fat": 60,
                "notes": "Plant-based protein sources included"
            }
        else:
            return {
                "breakfast": "Greek yogurt with berries and granola (1 cup yogurt, 1/2 cup berries, 1/4 cup granola)",
                "lunch": "Grilled chicken salad with mixed greens (4 oz chicken, 2 cups mixed greens, olive oil dressing)",
                "dinner": "Baked salmon with roasted vegetables (4 oz salmon, 2 cups mixed vegetables)",
                "total_calories": 1600,
                "total_carbs": 150,
                "total_protein": 120,
                "total_fat": 50,
                "notes": "Balanced macronutrients for general health"
            }
    
    def _fallback_nutrition(self) -> Dict[str, float]:
        """Fallback nutrition values if LLM fails"""
        return {
            "carbs": 30.0,
            "protein": 15.0,
            "fat": 10.0,
            "calories": 250.0
        }
    
    def answer_general_question(self, question: str) -> str:
        """Answer general health and nutrition questions"""
        prompt = f"""
        You are a helpful health and nutrition assistant. Answer the following question 
        with accurate, helpful information. Keep responses concise but informative.
        
        Question: {question}
        
        If the question is not related to health, nutrition, or wellness, politely redirect 
        the user back to health-related topics.
        """
        
        return self.generate_response(prompt)