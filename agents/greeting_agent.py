# agents/greeting_agent.py
from agno.agent import Agent
from agno.models.google import Gemini
from typing import Dict, Any, Optional
import sys
from dotenv import load_dotenv
import os

load_dotenv()

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from utils.database import DatabaseManager

class GreetingAgent(Agent):
    def __init__(self):
        super().__init__(
            name="GreetingAgent",
            model=Gemini(
            id=os.environ['DEFAULT_MODEL'],
            vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI'],
            project_id=os.environ['GOOGLE_CLOUD_PROJECT'],
            location=os.environ['GOOGLE_CLOUD_LOCATION'],
            api_key=os.environ.get('GOOGLE_API_KEY')),
            description="Validates user ID and provides personalized greetings",
            instructions=[
                "You are a friendly health assistant that helps users log in to their health tracking system.",
                "Always validate user IDs before proceeding with any interactions.",
                "Provide warm, personalized greetings using the user's name and location.",
                "If a user ID is invalid, help them find the correct ID by searching their name.",
                "Be encouraging and supportive in all interactions."
            ],
            show_tool_calls=True,
            markdown=True
        )
        self.db = DatabaseManager()
        self.current_user = None
        
        # Add custom tools
        self.add_tool(self.validate_user_id)
        self.add_tool(self.search_users_by_name)
        self.add_tool(self.get_current_user)
    
    def validate_user_id(self, user_id: str) -> Dict[str, Any]:
        """
        Validate a user ID against the database
        
        Args:
            user_id: The user ID to validate
            
        Returns:
            Dict containing user data if valid, or error message if invalid
        """
        user_data = self.db.validate_user_id(user_id.strip())
        
        if user_data:
            self.current_user = user_data
            return {
                "status": "success",
                "message": f"Welcome back, {user_data['name']} from {user_data['city']}!",
                "user_data": user_data
            }
        else:
            return {
                "status": "error",
                "message": "Invalid user ID. Please check your ID or tell me your name so I can help you find it."
            }
    
    def search_users_by_name(self, name: str) -> Dict[str, Any]:
        """
        Search for users by name
        
        Args:
            name: The name to search for
            
        Returns:
            Dict containing matching users or no matches message
        """
        users = self.db.get_user_by_name(name.strip())
        
        if users:
            return {
                "status": "success",
                "message": f"Found {len(users)} user(s) matching '{name}':",
                "users": users
            }
        else:
            return {
                "status": "error",
                "message": f"No users found matching '{name}'. Please try a different name or check the spelling."
            }
    
    def get_current_user(self) -> Dict[str, Any]:
        """
        Get the currently logged in user
        
        Returns:
            Dict containing current user data or None if no user logged in
        """
        if self.current_user:
            return {
                "status": "success",
                "user_data": self.current_user
            }
        else:
            return {
                "status": "error",
                "message": "No user currently logged in. Please provide your user ID first."
            }
    
    def is_user_authenticated(self) -> bool:
        """Check if a user is currently authenticated"""
        return self.current_user is not None
    
    def get_authenticated_user_id(self) -> Optional[str]:
        """Get the authenticated user's ID"""
        return self.current_user['user_id'] if self.current_user else None

# Convenience function to create the agent
def create_greeting_agent():
    return GreetingAgent()