# agents/interrupt_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, Optional, List
import sys
from dotenv import load_dotenv
import os
import re

load_dotenv()

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager

class InterruptAgent(Agent):
    def __init__(self):
        super().__init__(
            name="InterruptAgent",
            model=Gemini(
                id=os.environ['DEFAULT_MODEL'],
                vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
                project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
                location=os.environ['GOOGLE_CLOUD_LOCATION'],
                api_key=os.environ.get('GOOGLE_API_KEY')
            ),
            description="General Q&A assistant that handles interruptions and unrelated queries during health tracking interactions",
            instructions=[
                "You are a helpful general knowledge assistant that can interrupt any ongoing health tracking conversation to answer questions.",
                "Handle any general questions, FAQs, or unrelated queries that users might have.",
                "After answering, gracefully guide users back to their previous health tracking task or main menu.",
                "Be informative, concise, and helpful while maintaining a friendly tone.",
                "If you don't know something, be honest about it and suggest alternatives.",
                "Always remember the context of what the user was doing before the interruption."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.previous_context = None
        self.authenticated_user_id = None
        self.current_user_name = None
        self.available_agents = [
            "Greeting Agent", "Mood Tracker", "CGM Monitor", 
            "Food Intake Tracker", "Meal Planner"
        ]
        
        # Add custom tools
        self.add_tool(self.answer_general_question)
        self.add_tool(self.handle_faq)
        self.add_tool(self.set_previous_context)
        self.add_tool(self.get_routing_suggestions)
        self.add_tool(self.check_health_related_query)
    
    def set_previous_context(self, context: str, agent_name: str = None) -> Dict[str, Any]:
        """
        Set the previous context before handling an interruption
        
        Args:
            context: Description of what the user was doing
            agent_name: Name of the agent that was active
            
        Returns:
            Dict confirming context was set
        """
        self.previous_context = {
            "context": context,
            "agent": agent_name,
            "timestamp": "now"
        }
        
        return {
            "status": "success",
            "message": f"Context set: {context}",
            "previous_agent": agent_name
        }
    def handle_faq(self, question: str) -> Dict[str, Any]:
        """
        Handle frequently asked questions about the health tracking system
        
        Args:
            question: The user's question
            
        Returns:
            Dict containing FAQ answer or indication that it's not an FAQ
        """
        question_lower = question.lower()
        
        # Common FAQ patterns
        faqs = {
            "how to use": {
                "answer": "This health tracking system helps you monitor mood, glucose levels, food intake, and plan meals. Start by logging in with your user ID, then choose what you'd like to track.",
                "routing": "Would you like to go to the main menu to start tracking?"
            },
            "what can you do": {
                "answer": "I can help you: 1) Track your mood and emotions, 2) Monitor glucose readings, 3) Log food intake, 4) Plan healthy meals, 5) Answer general questions like this one!",
                "routing": "Which of these would you like to try?"
            },
            "forgot id": {
                "answer": "No problem! I can help you find your user ID by searching with your name. Just tell me your name and I'll look it up.",
                "routing": "Would you like me to help you find your user ID now?"
            },
            "data privacy": {
                "answer": "Your health data is stored securely and only used for your personal tracking and meal planning. We don't share your information with third parties.",
                "routing": "Do you have any other privacy concerns, or would you like to continue with health tracking?"
            },
            "glucose range": {
                "answer": "Normal glucose levels are typically between 80-300 mg/dL for our tracking purposes. The system will alert you if readings are outside this range.",
                "routing": "Would you like to log a glucose reading now?"
            },
            "meal planning": {
                "answer": "The meal planner creates personalized 3-meal daily plans based on your dietary preferences, medical conditions, recent mood, and glucose levels.",
                "routing": "Would you like to generate a meal plan?"
            }
        }
        
        # Find matching FAQ
        for key, faq_data in faqs.items():
            if key in question_lower:
                return {
                    "status": "success",
                    "is_faq": True,
                    "question": question,
                    "answer": faq_data["answer"],
                    "routing_suggestion": faq_data["routing"]
                }
        
        return {
            "status": "not_found",
            "is_faq": False,
            "message": "This doesn't match our common FAQs. I'll treat it as a general question."
        }

    def check_health_related_query(self, query: str) -> Dict[str, Any]:
        """
        Check if a query is related to health tracking features
        
        Args:
            query: The user's query
            
        Returns:
            Dict indicating if it's health-related and suggesting appropriate agent
        """
        query_lower = query.lower()
        
        # Agent-specific keywords
        agent_mapping = {
            "mood": ["mood", "feeling", "emotion", "happy", "sad", "excited", "tired", "anxious", "stressed"],
            "glucose": ["glucose", "blood sugar", "cgm", "diabetes", "sugar level", "mg/dl"],
            "food": ["food", "eat", "meal", "lunch", "dinner", "breakfast", "calories", "nutrition"],
            "meal_plan": ["meal plan", "diet", "recipe", "menu", "dietary", "vegetarian", "vegan"],
            "greeting": ["login", "user id", "sign in", "account", "profile"]
        }
        
        for agent, keywords in agent_mapping.items():
            if any(keyword in query_lower for keyword in keywords):
                return {
                    "status": "success",
                    "is_health_related": True,
                    "suggested_agent": agent,
                    "confidence": "high"
                }
        
        return {
            "status": "success",
            "is_health_related": False,
            "suggested_agent": None,
            "confidence": "low"
        }


    def get_routing_suggestions(self) -> Dict[str, Any]:
        """
        Get suggestions for where the user can go next
        
        Returns:
            Dict containing routing options
        """
        suggestions = []
        
        if self.previous_context:
            suggestions.append(f"Continue with {self.previous_context.get('agent', 'previous task')}")
        
        suggestions.extend([
            "Go to main menu",
            "Track your mood",
            "Log glucose reading", 
            "Record food intake",
            "Generate meal plan",
            "Ask another question"
        ])
        
        return {
            "status": "success",
            "suggestions": suggestions,
            "previous_context": self.previous_context
        }

    def answer_general_question(self, question: str) -> Dict[str, Any]:
        """
        Answer general knowledge questions with improved context awareness
        
        Args:
            question: The user's question
            
        Returns:
            Dict containing the answer
        """
        import re
        question_lower = question.lower().strip()
        
        # Check if it's health-related but not specific to our tracking system
        health_keywords = ['health', 'medical', 'doctor', 'medicine', 'symptoms', 'treatment', 'diet', 'exercise', 'nutrition', 'wellness', 'fitness']
        is_health_related = any(keyword in question_lower for keyword in health_keywords)
        
        # Check for emotional expressions or mood-related content
        emotional_patterns = [
            r"i'?m\s+(stupid|dumb|worthless|useless|terrible|awful|pathetic)",
            r"i\s+feel\s+like",
            r"i'?m\s+(so|really|very|extremely)\s+(sad|depressed|angry|frustrated|upset|down|low)",
            r"having\s+a\s+(bad|rough|terrible|awful)\s+day",
            r"life\s+is\s+(hard|difficult|tough)"
        ]
        
        # Check for food-related content
        food_patterns = [
            r"i\s+(ate|had|consumed|eaten)\s+",
            r"just\s+(ate|had|finished)\s+",
            r"for\s+(breakfast|lunch|dinner)\s+i\s+"
        ]
        
        # Check for glucose-related content
        glucose_patterns = [
            r"\d+\s*mg",
            r"blood\s+sugar\s+is\s+\d+",
            r"glucose\s+(reading|level)\s+\d+"
        ]
        
        # Check for negative expressions directed at me or random statements
        negative_expressions = [
            r"you\s+are\s+(stupid|dumb|useless|terrible|awful|bad)",
            r"this\s+is\s+(stupid|dumb|useless|terrible|awful)",
            r"(stupid|dumb|useless|terrible|awful)$"
        ]
        
        # Generate more natural responses
        routing_suggestion = None
        answer = ""
        
        # Handle emotional expressions
        if any(re.search(pattern, question_lower) for pattern in emotional_patterns):
            answer = "It sounds like you might be going through something difficult. Would you like to track your mood? I can help you log how you're feeling."
            routing_suggestion = "mood_tracking"
        
        # Handle food mentions
        elif any(re.search(pattern, question_lower) for pattern in food_patterns):
            answer = "I noticed you mentioned food. Would you like to log what you've eaten? I can help track your meals and nutrition."
            routing_suggestion = "food_logging"
        
        # Handle glucose mentions
        elif any(re.search(pattern, question_lower) for pattern in glucose_patterns):
            answer = "I see some numbers that look like glucose readings. Would you like to log a blood sugar reading?"
            routing_suggestion = "glucose_logging"
        
        # Handle negative expressions more naturally
        elif any(re.search(pattern, question_lower) for pattern in negative_expressions):
            if self.current_user_name:
                answer = f"No worries, {self.current_user_name}! I'm here to help you with your health tracking. What would you like to do today?"
            else:
                answer = "That's okay! I'm here to help you track your health. What would you like to work on?"
        
        # Handle health-related questions
        elif is_health_related:
            answer = "I can help with general health information, though for specific medical advice, it's best to consult healthcare professionals."
        
        # Handle random statements or unclear input
        else:
            if self.current_user_name:
                answer = f"I'm here to help you track your health, {self.current_user_name}. What would you like to do today?"
            else:
                answer = "I'm your health tracking assistant. I can help you log your mood, track food, monitor glucose levels, or plan meals."
        
        return {
            "status": "success",
            "question": question,
            "answer": answer,
            "is_health_related": is_health_related,
            "user_context": self.current_user_name is not None,
            "routing_suggestion": routing_suggestion
        }
    
    def route_to_appropriate_agent(self, user_input: str) -> Dict[str, Any]:
        """
        Determine which agent would be most appropriate for the user's input
        
        Args:
            user_input: The user's input to analyze
            
        Returns:
            Dict containing routing recommendation
        """
        input_lower = user_input.lower()
        
        # Agent routing keywords
        routing_map = {
            "mood_tracker": {
                "keywords": ["mood", "feeling", "emotion", "happy", "sad", "excited", "tired", "anxious", "stressed", "depressed", "angry"],
                "agent": "mood_tracker",
                "message": "It sounds like you might want to track your mood. Would you like to log how you're feeling today?"
            },
            "cgm_monitor": {
                "keywords": ["glucose", "blood sugar", "cgm", "diabetes", "sugar level", "mg/dl", "blood test", "glucose reading"],
                "agent": "cgm_monitor", 
                "message": "It looks like you're interested in glucose monitoring. Would you like to log a glucose reading?"
            },
            "food_intake": {
                "keywords": ["food", "eat", "ate", "meal", "lunch", "dinner", "breakfast", "snack", "calories", "nutrition", "hungry"],
                "agent": "food_intake",
                "message": "I see you're talking about food! Would you like to log what you've eaten or are planning to eat?"
            },
            "meal_planner": {
                "keywords": ["meal plan", "diet plan", "recipe", "menu", "dietary", "vegetarian", "vegan", "plan meals", "what to eat"],
                "agent": "meal_planner",
                "message": "It sounds like you need help with meal planning! Would you like me to generate a personalized meal plan for you?"
            },
            "main_menu": {
                "keywords": ["menu", "options", "what can", "help", "start over", "begin", "main"],
                "agent": "main_menu",
                "message": "Would you like to see the main menu to choose what you'd like to track or plan today?"
            }
        }
        
        # Check for routing matches
        for route_key, route_info in routing_map.items():
            if any(keyword in input_lower for keyword in route_info["keywords"]):
                return {
                    "status": "success",
                    "routing_found": True,
                    "recommended_agent": route_info["agent"],
                    "message": route_info["message"],
                    "routing_suggestion": route_info["message"]
                }
        
        # No specific routing found
        return {
            "status": "success", 
            "routing_found": False,
            "recommended_agent": None,
            "message": "I can help answer your question, and then you can choose what you'd like to do next.",
            "routing_suggestion": None
        }
    
    def set_authenticated_user(self, user_id: str):
        """Set the authenticated user for this session"""
        self.authenticated_user_id = user_id
        user_data = self.db.validate_user_id(user_id)
        if user_data:
            self.current_user_name = user_data['name']
    
    def explain_system_features(self) -> Dict[str, Any]:
        """Explain all available system features"""
        features_explanation = """
🏥 **Health Agent System Features**

**🎭 Mood Tracking**
• Log your daily mood with descriptive labels
• View mood trends and rolling averages
• Get personalized mood-boosting suggestions
• Track patterns over time

**🩸 Glucose Monitoring (CGM)**
• Log glucose readings with smart validation
• Get alerts for out-of-range readings
• Medical condition-aware target ranges
• Track glucose trends and time in range

**🍽️ Food Intake Tracking**
• Log meals with automatic nutrient analysis
• AI-powered food categorization
• Daily nutrition summaries
• Dietary preference considerations

**📋 Meal Planning**
• Generate personalized 3-meal daily plans
• Adapts to your medical conditions
• Considers recent mood and glucose data
• Customizable with shopping lists

**❓ General Q&A Assistant**
• Ask health and nutrition questions anytime
• Get answers without losing your place
• Helpful routing back to main features
• FAQ support for common questions

**🔐 Smart Authentication**
• Secure user ID validation
• Name-based user search
• Personalized greetings with location

**💡 Quick Commands:**
• "Track mood" - Log how you're feeling
• "Log glucose" - Record a CGM reading
• "Log meal" - Track food intake
• "Plan meals" - Generate meal suggestions
• "Show insights" - View health trends
• "Help" - See this feature list

What would you like to try?"""
        
        return {
            "status": "success",
            "explanation": features_explanation
        }
    
    def get_authenticated_user_id(self) -> Optional[str]:
        """Get the authenticated user's ID"""
        return self.authenticated_user_id
    
    def is_user_authenticated(self) -> bool:
        """Check if a user is currently authenticated"""
        return self.authenticated_user_id is not None

# Convenience function to create the agent
def create_interrupt_agent():
    return InterruptAgent()

# Example usage and testing
if __name__ == "__main__":
    agent = create_interrupt_agent()
    
    # Test user authentication
    auth_result = agent.set_authenticated_user("user123")
    print("Auth Test:", auth_result)
    
    # Test system features explanation
    features_result = agent.explain_system_features()
    print("Features Test:", features_result)
    
    # Test general question
    general_response = agent.answer_general_question("What is the capital of France?")
    print("General Question Test:", general_response)
    
    # Test routing
    routing_response = agent.route_to_appropriate_agent("I'm feeling sad today")
    print("Routing Test:", routing_response)