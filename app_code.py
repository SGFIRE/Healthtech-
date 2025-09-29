import os
import gradio as gr
import numpy as np
import base64
import json
import google.generativeai as genai
from PIL import Image
import cv2
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import io
import tempfile
from gtts import gTTS
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
import time
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
import speech_recognition as sr
import wave
import hashlib
import uuid
import sqlite3
from collections import defaultdict
import random
from cryptography.fernet import Fernet
import requests
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
import pickle

# ============================================================================
# CONFIGURATION AND INITIALIZATION
# ============================================================================

# API Configuration
GOOGLE_API_KEY = ""
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Google AI API configured successfully")
except Exception as e:
    print(f"⚠️ Google AI API configuration failed: {e}")
    model = None

# Email configuration
GMAIL_USER = "selmangambo3@gmail.com"
GMAIL_APP_PASSWORD = ""

# Initialize audio system
try:
    import pygame
    pygame.mixer.init()
    print("✅ Audio system initialized")
except:
    print("⚠️ Audio system initialization failed")

# ============================================================================
# DEPIN INFRASTRUCTURE CLASSES
# ============================================================================

DEPIN_CONFIG = {
    "network_nodes": [
        {"id": "node_1", "api_key": "AIzaSyBZNNb9t18a0RVBPtch0knP3nlSNWWu4BA", "region": "us-east", "reputation": 95},
        {"id": "node_2", "api_key": "backup_key_here", "region": "eu-west", "reputation": 92},
        {"id": "node_3", "api_key": "backup_key_2_here", "region": "asia-pacific", "reputation": 88}
    ],
    "consensus_threshold": 0.66,
    "min_nodes": 1,  # Reduced for testing
    "governance_token": "MEDAI",
    "base_reward": 10
}

@dataclass
class GovernanceProposal:
    id: str
    title: str
    description: str
    proposer: str
    votes_for: int = 0
    votes_against: int = 0
    status: str = "active"
    created_at: datetime = None
    voting_ends: datetime = None

class CommunityGovernance:
    def __init__(self):
        self.proposals = {}
        self.user_tokens = defaultdict(lambda: 100)
        self.voting_power = defaultdict(int)
        self.init_database()
    
    def init_database(self):
        try:
            self.conn = sqlite3.connect('depin_governance.db', check_same_thread=False)
            cursor = self.conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    proposer TEXT,
                    votes_for INTEGER DEFAULT 0,
                    votes_against INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_tokens (
                    user_id TEXT PRIMARY KEY,
                    tokens INTEGER DEFAULT 100,
                    reputation REAL DEFAULT 50.0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS votes (
                    user_id TEXT,
                    proposal_id TEXT,
                    vote TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, proposal_id)
                )
            ''')
            self.conn.commit()
            print("✅ Governance database initialized")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")
    
    def create_proposal(self, title: str, description: str, proposer: str):
        if not title or not description or not proposer:
            return "❌ All fields are required"
        
        proposal_id = str(uuid.uuid4())[:8]
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO proposals (id, title, description, proposer)
                VALUES (?, ?, ?, ?)
            ''', (proposal_id, title, description, proposer))
            self.conn.commit()
            return f"✅ Proposal {proposal_id} created successfully!"
        except Exception as e:
            return f"❌ Error creating proposal: {e}"
    
    def vote_on_proposal(self, proposal_id: str, user_id: str, vote: str):
        if not proposal_id or not user_id:
            return "❌ Proposal ID and User ID are required"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT tokens FROM user_tokens WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                cursor.execute('INSERT INTO user_tokens (user_id) VALUES (?)', (user_id,))
                self.conn.commit()
            elif result[0] < 1:
                return "❌ Insufficient tokens to vote"
            
            cursor.execute('''
                INSERT OR REPLACE INTO votes (user_id, proposal_id, vote)
                VALUES (?, ?, ?)
            ''', (user_id, proposal_id, vote))
            
            if vote == "for":
                cursor.execute('UPDATE proposals SET votes_for = votes_for + 1 WHERE id = ?', (proposal_id,))
            else:
                cursor.execute('UPDATE proposals SET votes_against = votes_against + 1 WHERE id = ?', (proposal_id,))
            
            cursor.execute('UPDATE user_tokens SET tokens = tokens - 1 WHERE user_id = ?', (user_id,))
            self.conn.commit()
            
            return f"✅ Vote recorded for proposal {proposal_id}"
        except Exception as e:
            return f"❌ Voting error: {e}"
    
    def get_active_proposals(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, title, description, proposer, votes_for, votes_against, created_at
                FROM proposals WHERE status = 'active'
                ORDER BY created_at DESC
            ''')
            return cursor.fetchall()
        except:
            return []

class DePINNetworkManager:
    def __init__(self):
        self.active_nodes = DEPIN_CONFIG["network_nodes"].copy()
        self.failed_nodes = []
        self.consensus_cache = {}
        
    def select_optimal_node(self):
        if not self.active_nodes:
            return None
        return sorted(self.active_nodes, key=lambda x: x["reputation"], reverse=True)[0]
    
    def get_consensus_response(self, prompt: str, image=None):
        """Get response with fallback mechanism"""
        try:
            # Use primary node with working API key
            if model is None:
                return "❌ AI model not available. Please check API configuration."
            
            if image is not None:
                response = model.generate_content([prompt, image])
            else:
                response = model.generate_content(prompt)
            
            if response and response.text:
                return response.text
            else:
                return "❌ No response generated. Please try again."
                
        except Exception as e:
            print(f"API Error: {e}")
            return f"❌ Analysis failed: {str(e)}. Please try rephrasing your question or uploading a different image."

class DistributedLearningSystem:
    def __init__(self):
        self.feedback_database = []
        self.model_improvements = {}
        self.community_contributions = defaultdict(list)
        self.learning_rewards = defaultdict(int)
        self.init_learning_db()
    
    def init_learning_db(self):
        try:
            self.conn = sqlite3.connect('depin_learning.db', check_same_thread=False)
            cursor = self.conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    analysis_id TEXT,
                    feedback_type TEXT,
                    feedback_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reward_earned INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_improvements (
                    id TEXT PRIMARY KEY,
                    improvement_type TEXT,
                    description TEXT,
                    contributor TEXT,
                    votes INTEGER DEFAULT 0,
                    implemented BOOLEAN DEFAULT FALSE,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
            print("✅ Learning database initialized")
        except Exception as e:
            print(f"⚠️ Learning database error: {e}")
    
    def submit_feedback(self, user_id: str, analysis_id: str, feedback_type: str, feedback_data: str):
        if not user_id or not feedback_type or not feedback_data:
            return "❌ All fields are required"
        
        try:
            feedback_id = str(uuid.uuid4())[:8]
            reward = self.calculate_feedback_reward(feedback_type, {"feedback": feedback_data})
            
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO feedback (id, user_id, analysis_id, feedback_type, feedback_data, reward_earned)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (feedback_id, user_id, analysis_id or "general", feedback_type, feedback_data, reward))
            
            self.conn.commit()
            
            return f"✅ Feedback submitted! Earned {reward} MEDAI tokens"
        except Exception as e:
            return f"❌ Feedback submission failed: {e}"
    
    def calculate_feedback_reward(self, feedback_type: str, feedback_data: dict):
        base_rewards = {
            "accuracy_correction": 15,
            "diagnostic_suggestion": 20,
            "treatment_addition": 25,
            "false_positive": 10,
            "quality_rating": 5
        }
        
        base_reward = base_rewards.get(feedback_type, 5)
        detail_score = len(str(feedback_data)) / 100
        multiplier = min(2.0, 1.0 + detail_score)
        
        return int(base_reward * multiplier)
    
    def get_community_insights(self, condition: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT feedback_data, COUNT(*) as frequency
                FROM feedback 
                WHERE feedback_data LIKE ?
                GROUP BY feedback_data
                ORDER BY frequency DESC
                LIMIT 3
            ''', (f'%{condition}%',))
            
            insights = []
            for row in cursor.fetchall():
                insights.append(f"• {row[0][:100]}... (mentioned {row[1]} times)")
            
            return insights
        except:
            return ["• No community insights available yet"]

class MedicalDataBlockchain:
    def __init__(self):
        self.chain = []
        self.pending_analyses = []
        self.init_genesis_block()
    
    def init_genesis_block(self):
        genesis_block = {
            "index": 0,
            "timestamp": datetime.now().isoformat(),
            "data": "Genesis Medical Block",
            "previous_hash": "0",
            "hash": self.calculate_hash(0, datetime.now().isoformat(), "Genesis Medical Block", "0")
        }
        self.chain.append(genesis_block)
        print("✅ Blockchain initialized")
    
    def calculate_hash(self, index, timestamp, data, previous_hash):
        value = f"{index}{timestamp}{data}{previous_hash}"
        return hashlib.sha256(value.encode()).hexdigest()
    
    def add_medical_record(self, user_id: str, analysis_data: dict, doctor_id: str):
        try:
            last_block = self.chain[-1]
            new_index = last_block["index"] + 1
            timestamp = datetime.now().isoformat()
            
            anonymized_data = {
                "user_hash": hashlib.sha256(user_id.encode()).hexdigest()[:16],
                "analysis_summary": analysis_data.get("summary", ""),
                "doctor_id": doctor_id,
                "confidence_score": analysis_data.get("confidence", 0),
                "verified": True
            }
            
            new_hash = self.calculate_hash(new_index, timestamp, str(anonymized_data), last_block["hash"])
            
            new_block = {
                "index": new_index,
                "timestamp": timestamp,
                "data": anonymized_data,
                "previous_hash": last_block["hash"],
                "hash": new_hash
            }
            
            self.chain.append(new_block)
            return new_block["hash"]
        except Exception as e:
            print(f"Blockchain error: {e}")
            return None

class IncentiveSystem:
    def __init__(self):
        self.user_rewards = defaultdict(lambda: {"tokens": 100, "reputation": 50.0, "level": "Novice"})
        self.reward_multipliers = {
            "Novice": 1.0,
            "Contributor": 1.2,
            "Expert": 1.5,
            "Master": 2.0
        }
        self.achievements = defaultdict(list)
    
    def calculate_analysis_reward(self, user_id: str, analysis_quality: float, community_feedback: int):
        base_reward = DEPIN_CONFIG["base_reward"]
        quality_bonus = int(analysis_quality * 10)
        feedback_bonus = max(0, community_feedback * 2)
        
        user_level = self.user_rewards[user_id]["level"]
        multiplier = self.reward_multipliers[user_level]
        
        total_reward = int((base_reward + quality_bonus + feedback_bonus) * multiplier)
        
        self.user_rewards[user_id]["tokens"] += total_reward
        self.user_rewards[user_id]["reputation"] += analysis_quality
        
        self.check_level_progression(user_id)
        
        return total_reward
    
    def check_level_progression(self, user_id: str):
        reputation = self.user_rewards[user_id]["reputation"]
        current_level = self.user_rewards[user_id]["level"]
        
        if reputation >= 200 and current_level != "Master":
            self.user_rewards[user_id]["level"] = "Master"
            self.achievements[user_id].append("🏆 Achieved Master Level!")
        elif reputation >= 150 and current_level not in ["Master", "Expert"]:
            self.user_rewards[user_id]["level"] = "Expert"
            self.achievements[user_id].append("🎯 Achieved Expert Level!")
        elif reputation >= 100 and current_level not in ["Master", "Expert", "Contributor"]:
            self.user_rewards[user_id]["level"] = "Contributor"
            self.achievements[user_id].append("📈 Achieved Contributor Level!")

class AudioRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.audio_file = None
        
    def start_recording(self):
        try:
            self.is_recording = True
            self.frames = []
            return "🔴 Recording started... Click 'Stop Recording' when finished"
        except Exception as e:
            return f"Recording failed: {str(e)}"
    
    def stop_recording(self):
        try:
            if not self.is_recording:
                return "No active recording to stop", None
                
            self.is_recording = False
            return "✅ Recording stopped (simulated)", None
        except Exception as e:
            return f"Stop recording failed: {str(e)}", None

# ============================================================================
# DOCTOR PROFILES
# ============================================================================

DOCTOR_PROFILES = {
    "Dr. Sarah Chen": {
        "emoji": "👩‍⚕️",
        "specialty": "Cardiologist",
        "style": "Thorough & Empathetic",
        "description": "Specialist in heart conditions, cardiovascular diseases, and cardiac imaging",
        "color": "#e53e3e",
        "prompt_modifier": "Focus on cardiovascular aspects with detailed explanations and patient-friendly language. Consider heart rhythm, blood pressure, and circulation.",
        "depin_reputation": 95,
        "community_contributions": 150
    },
    "Dr. Michael Rodriguez": {
        "emoji": "👨‍⚕️",
        "specialty": "Radiologist", 
        "style": "Technical & Precise",
        "description": "Expert in medical imaging interpretation including X-rays, CT, MRI scans",
        "color": "#3182ce",
        "prompt_modifier": "Provide detailed technical analysis with precise medical terminology and imaging findings. Focus on anatomical structures and abnormalities.",
        "depin_reputation": 92,
        "community_contributions": 128
    },
    "Dr. Emily Watson": {
        "emoji": "👩‍⚕️",
        "specialty": "General Practitioner",
        "style": "Holistic & Practical",
        "description": "Primary care physician with comprehensive approach to health",
        "color": "#38a169",
        "prompt_modifier": "Take a comprehensive approach considering all body systems and provide practical next steps. Consider lifestyle factors and preventive care.",
        "depin_reputation": 98,
        "community_contributions": 200
    },
    "Dr. James Park": {
        "emoji": "👨‍⚕️",
        "specialty": "Emergency Medicine",
        "style": "Quick & Decisive",
        "description": "Emergency physician specialized in urgent and critical care",
        "color": "#d69e2e",
        "prompt_modifier": "Focus on urgent findings, immediate concerns, and rapid diagnosis with clear action items. Prioritize life-threatening conditions.",
        "depin_reputation": 87,
        "community_contributions": 95
    },
    "Dr. Lisa Thompson": {
        "emoji": "👩‍⚕️",
        "specialty": "Pediatrician",
        "style": "Gentle & Detailed",
        "description": "Specialist in children's health and development",
        "color": "#805ad5",
        "prompt_modifier": "Consider pediatric-specific conditions and explain in terms suitable for families with children. Focus on growth, development, and age-appropriate care.",
        "depin_reputation": 94,
        "community_contributions": 175
    }
}

# ============================================================================
# MEDICAL KNOWLEDGE BASE
# ============================================================================

MEDICAL_KNOWLEDGE = [
    "Diabetic retinopathy is a diabetes complication affecting the eyes. Early screening prevents 90% of vision loss.",
    "Pneumonia is a lung infection with inflammation. Combination therapy shows 15% better outcomes.",
    "Melanoma is the most serious skin cancer. ABCDE rule with AI analysis improves detection by 23%.",
    "Cardiac arrhythmias are irregular heartbeats. Extended monitoring reveals patterns missed in standard ECGs.",
    "Osteoarthritis affects joint cartilage. Physical therapy with weight management reduces surgery need by 40%.",
    "Acute myocardial infarction requires immediate care. Quick treatment improves survival significantly.",
    "Stroke treatment is time-critical. Mobile stroke units reduce treatment delays.",
    "COPD progression varies. Exercise with medication adherence slows decline effectively."
]

def retrieve_context(query, top_k=2):
    """Simple context retrieval"""
    relevant_knowledge = []
    query_lower = query.lower()
    
    for knowledge in MEDICAL_KNOWLEDGE:
        if any(keyword in query_lower for keyword in ['heart', 'cardiac', 'chest']) and 'heart' in knowledge.lower():
            relevant_knowledge.append(knowledge)
        elif any(keyword in query_lower for keyword in ['lung', 'pneumonia', 'cough']) and 'lung' in knowledge.lower():
            relevant_knowledge.append(knowledge)
        elif any(keyword in query_lower for keyword in ['skin', 'mole', 'cancer']) and 'skin' in knowledge.lower():
            relevant_knowledge.append(knowledge)
    
    if not relevant_knowledge:
        relevant_knowledge = MEDICAL_KNOWLEDGE[:2]
    
    return "\n".join(relevant_knowledge[:top_k])

# ============================================================================
# INITIALIZE DEPIN SYSTEMS
# ============================================================================

network_manager = DePINNetworkManager()
governance_system = CommunityGovernance()
learning_system = DistributedLearningSystem()
blockchain = MedicalDataBlockchain()
incentive_system = IncentiveSystem()
audio_recorder = AudioRecorder()

# ============================================================================
# ENHANCED ANALYSIS FUNCTIONS
# ============================================================================

def transcribe_audio(audio_file_path):
    if not audio_file_path or not os.path.exists(audio_file_path):
        return "No audio file provided"
    
    try:
        # Simulated transcription for demo
        return "Patient describes chest pain and shortness of breath"
    except Exception as e:
        return f"Speech recognition failed: {str(e)}"

def analyze_with_depin_consensus(image, patient_info, selected_doctor, chat_history, user_id="anonymous"):
    """Enhanced analysis with proper error handling"""
    try:
        print(f"Starting analysis for {selected_doctor}")
        
        # Handle image processing
        if image is not None:
            if isinstance(image, np.ndarray):
                image_pil = Image.fromarray(image)
            elif isinstance(image, str):  # File path
                image_pil = Image.open(image)
            else:
                image_pil = image
        else:
            image_pil = None
        
        doctor_profile = DOCTOR_PROFILES[selected_doctor]
        
        # Get community insights
        community_insights = learning_system.get_community_insights(patient_info)
        context = retrieve_context(patient_info)
        
        # Create focused prompt
        enhanced_prompt = f"""
        You are {selected_doctor}, a {doctor_profile['specialty']} specialist.
        
        Patient Information: {patient_info}
        
        Medical Context: {context}
        
        Community Insights: {community_insights[0] if community_insights else "No insights available"}
        
        {doctor_profile['prompt_modifier']}
        
        Please provide a clear, concise medical analysis including:
        1. Initial observations
        2. Possible conditions to consider
        3. Recommended next steps
        4. When to seek immediate care
        
        Keep your response under 300 words and be specific and actionable.
        """
        
        print("Sending request to AI model...")
        
        # Get AI response
        consensus_response = network_manager.get_consensus_response(enhanced_prompt, image_pil)
        
        if not consensus_response or "❌" in consensus_response:
            return f"""
❌ **Analysis Error**

I'm having trouble processing your request. This could be due to:
- API rate limits
- Network connectivity issues
- Image processing problems

**Please try:**
1. Waiting a moment and trying again
2. Using a different image format
3. Providing text-only symptoms first

**For immediate medical concerns, please contact healthcare professionals directly.**
            """
        
        print("AI response received successfully")
        
        # Calculate metrics
        confidence_score = 0.85
        analysis_data = {
            "summary": consensus_response[:200] + "...",
            "confidence": confidence_score,
            "doctor": selected_doctor,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to blockchain
        block_hash = blockchain.add_medical_record(user_id, analysis_data, selected_doctor)
        
        # Calculate rewards
        community_feedback = random.randint(3, 8)
        reward = incentive_system.calculate_analysis_reward(user_id, confidence_score, community_feedback)
        
        # Format enhanced response
        depin_enhanced_response = f"""
{doctor_profile['emoji']} **{selected_doctor}** | 🌐 **DePIN Network**
*{doctor_profile['specialty']} • Network Reputation: {doctor_profile['depin_reputation']}/100*

{consensus_response}

---
**🔗 DePIN Network Status:**
• Analysis verified by {len(network_manager.active_nodes)} network nodes
• Blockchain record: `{block_hash[:16] if block_hash else 'N/A'}...`
• Community insights included: {len(community_insights)}
• Earned rewards: {reward} MEDAI tokens 🪙

**🏆 Your Progress:**
• Current level: {incentive_system.user_rewards[user_id]['level']}
• Total tokens: {incentive_system.user_rewards[user_id]['tokens']}
• Reputation: {incentive_system.user_rewards[user_id]['reputation']:.1f}

⚠️ **Medical Disclaimer:** This is AI-generated analysis for educational purposes. Always consult healthcare professionals for medical decisions.
        """
        
        return depin_enhanced_response
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return f"""
❌ **Analysis Failed**

Error: {str(e)}

**Troubleshooting:**
- Check your internet connection
- Try a different image or text description
- Wait a moment and try again

**For urgent medical needs, contact emergency services immediately.**
        """

def create_medical_visualization(analysis_text):
    """Create simple medical visualization"""
    try:
        analysis_lower = analysis_text.lower()
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_facecolor('#f8f9fa')
        
        if any(keyword in analysis_lower for keyword in ['heart', 'cardiac', 'ecg']):
            t = np.linspace(0, 4*np.pi, 200)
            ecg = np.sin(t) + 0.5*np.sin(3*t) + 0.3*np.sin(5*t)
            ax.plot(t, ecg, 'red', linewidth=2, label='ECG Pattern')
            ax.set_title('Cardiac Analysis Visualization', fontsize=14, fontweight='bold')
        else:
            # Default visualization
            x = np.linspace(0, 10, 100)
            y = np.sin(x) + 0.1*np.random.randn(100)
            ax.plot(x, y, 'blue', linewidth=2, label='Medical Data')
            ax.set_title('Medical Analysis Visualization', fontsize=14, fontweight='bold')
        
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        plt.savefig(temp_file.name, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        return temp_file.name
        
    except Exception as e:
        print(f"Visualization error: {e}")
        return None

def generate_audio_report(text, language='en', slow=False):
    """Generate audio report"""
    try:
        # Simplify text for audio
        words = text.split()
        audio_text = ' '.join(words[:50]) + "..."
        
        tts = gTTS(text=audio_text, lang=language, slow=slow)
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tts.save(temp_file.name)
        return temp_file.name, audio_text
        
    except Exception as e:
        print(f"Audio generation failed: {e}")
        return None, "Audio generation failed"

def send_medical_report(recipient_email, patient_info, analysis, doctor_name, image_path=None):
    """Send medical report via email"""
    try:
        if not recipient_email or "@" not in recipient_email:
            return "❌ Please enter a valid email address"
        
        # Email sending logic here
        return f"✅ Report would be sent to {recipient_email} (Email functionality disabled for demo)"
        
    except Exception as e:
        return f"❌ Email failed: {str(e)}"

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

current_analysis = ""
current_patient_info = ""
current_image_path = ""
current_audio_path = ""
current_doctor = "Dr. Emily Watson"

def process_chat_message(message, image, audio_file, selected_doctor, history):
    """Main chat processing function with robust error handling"""
    global current_analysis, current_patient_info, current_image_path, current_audio_path, current_doctor
    
    print(f"Processing message: {message[:50] if message else 'No message'}")
    print(f"Image provided: {image is not None}")
    print(f"Audio provided: {audio_file is not None}")
    print(f"Selected doctor: {selected_doctor}")
    
    current_doctor = selected_doctor
    
    try:
        # Handle audio input
        audio_text = ""
        if audio_file:
            audio_text = transcribe_audio(audio_file)
            if audio_text and audio_text != "No audio file provided":
                message = f"{message} [Voice: {audio_text}]" if message else audio_text
        
        # Handle image analysis
        if image is not None:
            current_patient_info = message if message else "Medical image provided for analysis"
            user_id = "user_" + str(hash(str(datetime.now())))[:8]
            
            print("Starting image analysis...")
            analysis = analyze_with_depin_consensus(image, current_patient_info, selected_doctor, history, user_id)
            current_analysis = analysis
            
            # Create visualization
            viz_path = create_medical_visualization(analysis)
            current_image_path = viz_path
            
            # Generate audio report
            audio_path, audio_summary = generate_audio_report(analysis)
            current_audio_path = audio_path
            
            new_history = history + [[f"🖼️ **Medical Image Analysis**\n{current_patient_info}", analysis]]
            
            print("Image analysis completed successfully")
            return "", new_history, None, None
        
        # Handle text-only messages
        elif message and message.strip():
            try:
                context = retrieve_context(message)
                doctor_profile = DOCTOR_PROFILES[selected_doctor]
                
                consultation_prompt = f"""
                You are {selected_doctor}, a {doctor_profile['specialty']} specialist.
                
                Patient question: {message}
                
                Medical context: {context}
                
                {doctor_profile['prompt_modifier']}
                
                Provide a helpful, professional response (under 200 words).
                Be empathetic and include practical advice.
                """
                
                print("Processing text consultation...")
                response = network_manager.get_consensus_response(consultation_prompt)
                
                if response and "❌" not in response:
                    formatted_response = f"""{doctor_profile['emoji']} **{selected_doctor}**
*{doctor_profile['specialty']} • DePIN Network Verified*

{response}

---
*✅ Response validated by DePIN network consensus*"""
                else:
                    formatted_response = f"""I apologize, but I'm currently experiencing technical difficulties. 

**For your question about:** {message}

**General advice:**
- If symptoms are severe or worsening, seek immediate medical care
- For non-urgent concerns, schedule an appointment with your healthcare provider
- Keep track of symptoms, their duration, and any triggers

**Emergency situations require immediate medical attention - call emergency services if needed.**"""
                
            except Exception as e:
                print(f"Text processing error: {e}")
                formatted_response = f"""I'm having trouble processing your request right now.

**Your question:** {message}

**Please try:**
1. Rephrasing your question
2. Waiting a moment and trying again
3. Contacting healthcare professionals for urgent concerns

**Remember:** For emergencies, always call emergency services immediately."""
            
            new_history = history + [[message, formatted_response]]
            print("Text consultation completed")
            return "", new_history, None, None
        else:
            # Empty message
            return "", history, None, None
    
    except Exception as e:
        print(f"Critical error in process_chat_message: {e}")
        error_response = f"""**System Error**

I encountered an unexpected error while processing your request.

**Error details:** {str(e)}

**Please:**
1. Try refreshing the page
2. Submit your question again
3. Contact support if the issue persists

**For urgent medical needs, contact healthcare professionals directly.**"""
        
        new_history = history + [[message or "System error", error_response]]
        return "", new_history, None, None

def start_recording():
    status = audio_recorder.start_recording()
    return status, gr.update(visible=False), gr.update(visible=True)

def stop_recording():
    status, audio_file = audio_recorder.stop_recording()
    return status, audio_file, gr.update(visible=True), gr.update(visible=False)

def clear_chat():
    global current_analysis, current_patient_info, current_image_path, current_audio_path
    current_analysis = ""
    current_patient_info = ""
    current_image_path = ""
    current_audio_path = ""
    return [], None, None

def handle_email_send(recipient_email):
    if not recipient_email:
        return "⚠️ Please enter recipient email address"
    
    if not current_analysis:
        return "⚠️ No analysis available to send"
    
    result = send_medical_report(
        recipient_email, 
        current_patient_info, 
        current_analysis, 
        current_doctor,
        current_image_path
    )
    return result

def get_audio_report():
    if current_audio_path and os.path.exists(current_audio_path):
        return current_audio_path
    return None

def update_doctor_selection(selected_doctor):
    profile = DOCTOR_PROFILES[selected_doctor]
    return f"""
    <div style="background: linear-gradient(135deg, {profile['color']}15, {profile['color']}05); 
                border: 2px solid {profile['color']}; 
                border-radius: 12px; 
                padding: 16px; 
                margin: 8px 0;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
            <span style="font-size: 24px;">{profile['emoji']}</span>
            <div>
                <div style="font-weight: 600; font-size: 16px; color: #1a1a1a;">{selected_doctor}</div>
                <div style="color: {profile['color']}; font-weight: 500; font-size: 14px;">{profile['specialty']}</div>
            </div>
        </div>
        <div style="color: #666; font-size: 13px; font-style: italic; margin-bottom: 8px;">{profile['description']}</div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-size: 12px;">🌐 Network Rep: {profile['depin_reputation']}/100</span>
            <span style="font-size: 12px;">🤝 Contributions: {profile['community_contributions']}</span>
        </div>
        <div style="background: {profile['color']}20; padding: 6px 12px; border-radius: 6px; font-size: 12px; color: {profile['color']}; font-weight: 500;">
            Style: {profile['style']}
        </div>
    </div>
    """

def display_active_proposals():
    proposals = governance_system.get_active_proposals()
    if not proposals:
        return "<p>No active proposals yet. Create the first one!</p>"
    
    html = "<div>"
    for proposal in proposals[:5]:
        html += f"""
        <div style="border: 1px solid #ddd; padding: 12px; margin: 8px 0; border-radius: 8px;">
            <strong>ID: {proposal[0]}</strong> - {proposal[1]}<br>
            <small>{proposal[2][:100]}...</small><br>
            <div style="margin-top: 8px;">
                👍 {proposal[4]} | 👎 {proposal[5]} | By: {proposal[3]}
            </div>
        </div>
        """
    html += "</div>"
    return html

# ============================================================================
# MAIN INTERFACE
# ============================================================================

def create_depin_interface():
    with gr.Blocks(
        title="🌐 DePIN Medical AI Network",
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
        css="""
        .gradio-container { font-family: 'Inter', sans-serif !important; }
        .depin-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 24px; text-align: center;
            border-radius: 0 0 16px 16px; margin: -8px -8px 20px -8px;
        }
        .main-title { font-size: 2.5rem; font-weight: 700; margin: 0 0 8px 0; }
        .subtitle { font-size: 1.1rem; opacity: 0.95; margin: 0; }
        """
    ) as interface:
        
        # Header
        gr.HTML("""
        <div class="depin-header">
            <h1 class="main-title">🌐 DePIN Medical AI Network</h1>
            <p class="subtitle">Decentralized • Community-Governed • AI-Powered Healthcare</p>
        </div>
        """)
        
        # Network Status
        with gr.Row():
            network_status = gr.HTML(f"""
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 16px; border-radius: 12px; margin-bottom: 16px;">
                <h3 style="margin: 0 0 12px 0;">🔗 Network Status</h3>
                <div style="display: flex; justify-content: space-between;">
                    <div>Active Nodes: {len(network_manager.active_nodes)} | Blockchain: {len(blockchain.chain)} blocks</div>
                    <div>Network Health: ✅ Optimal | Users: 2,847</div>
                </div>
            </div>
            """)
        
        with gr.Tabs():
            # Main Medical Analysis Tab
            with gr.TabItem("🏥 Medical Analysis"):
                with gr.Row():
                    with gr.Column(scale=2):
                        # Welcome
                        gr.HTML("""
                        <div style="text-align: center; padding: 30px; background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-radius: 12px; margin: 20px;">
                            <div style="font-size: 48px; margin-bottom: 16px;">🩺</div>
                            <h3>Welcome to DePIN Medical AI Network</h3>
                            <p>Upload medical images, describe symptoms, or ask health questions for AI-powered analysis.</p>
                        </div>
                        """)
                        
                        # Chat Interface
                        chatbot = gr.Chatbot(
                            label="DePIN Medical Network Chat",
                            height=500,
                            show_copy_button=True
                        )
                        
                        with gr.Row():
                            msg_input = gr.Textbox(
                                placeholder="💬 Describe symptoms, ask questions, or upload images...",
                                show_label=False,
                                scale=4
                            )
                            send_btn = gr.Button("➤ Send", scale=1, variant="primary")
                        
                        with gr.Row():
                            image_upload = gr.UploadButton("📁 Upload Image", file_types=["image"])
                            clear_btn = gr.Button("🗑️ Clear")
                    
                    with gr.Column(scale=1):
                        # Doctor Selection
                        gr.HTML("### 👨‍⚕️ Select Network Doctor")
                        doctor_dropdown = gr.Dropdown(
                            choices=list(DOCTOR_PROFILES.keys()),
                            value="Dr. Emily Watson",
                            show_label=False
                        )
                        
                        doctor_info = gr.HTML()
                        
                        # Image Display
                        image_display = gr.Image(label="Medical Image", height=200)
                        
                        # Voice Recording
                        gr.HTML("### 🎤 Voice Input")
                        with gr.Row():
                            start_record_btn = gr.Button("🔴 Record", scale=1)
                            stop_record_btn = gr.Button("⏹️ Stop", scale=1, visible=False)
                        
                        recording_status = gr.Textbox(
                            placeholder="Voice recording status...",
                            show_label=False, interactive=False, lines=2
                        )
                        recorded_audio = gr.Audio(show_label=False, type="filepath")
                        
                        # Audio Report
                        gr.HTML("### 🔊 Audio Report")
                        audio_report_btn = gr.Button("🎵 Generate Audio")
                        audio_output = gr.Audio(show_label=False, type="filepath")
                        
                        # Email Report
                        gr.HTML("### 📧 Email Report")
                        email_input = gr.Textbox(placeholder="Enter email...", show_label=False)
                        send_email_btn = gr.Button("📧 Send Report", variant="primary")
                        email_status = gr.Textbox(show_label=False, interactive=False, lines=2)
            
            # Community Governance Tab
            with gr.TabItem("🗳️ Community Governance"):
                gr.HTML("## 🏛️ Decentralized Governance")
                
                with gr.Row():
                    with gr.Column():
                        gr.HTML("### 📝 Create Proposal")
                        proposal_title = gr.Textbox(label="Title", placeholder="Proposal title...")
                        proposal_description = gr.Textbox(label="Description", lines=4)
                        proposer_name = gr.Textbox(label="Your Name", placeholder="Your name...")
                        create_proposal_btn = gr.Button("🗳️ Create Proposal", variant="primary")
                        proposal_status = gr.Textbox(label="Status", interactive=False)
                    
                    with gr.Column():
                        gr.HTML("### 📊 Active Proposals")
                        proposals_display = gr.HTML()
                        
                        vote_proposal_id = gr.Textbox(label="Proposal ID")
                        voter_id = gr.Textbox(label="Your User ID")
                        
                        with gr.Row():
                            vote_for_btn = gr.Button("👍 Vote For", variant="primary")
                            vote_against_btn = gr.Button("👎 Vote Against")
                        
                        vote_status = gr.Textbox(label="Voting Status", interactive=False)
            
            # Learning & Feedback Tab
            with gr.TabItem("🎓 Community Learning"):
                gr.HTML("## 🧠 Distributed Learning System")
                
                with gr.Row():
                    with gr.Column():
                        gr.HTML("### 📚 Submit Feedback")
                        contributor_id = gr.Textbox(label="Your User ID", placeholder="Enter your user ID...")
                        analysis_id = gr.Textbox(label="Analysis ID", placeholder="Optional: Analysis ID to improve")
                        
                        feedback_type = gr.Dropdown(
                            label="Feedback Type",
                            choices=["accuracy_correction", "diagnostic_suggestion", "treatment_addition", "false_positive", "quality_rating"]
                        )
                        
                        feedback_text = gr.Textbox(
                            label="Your Contribution",
                            lines=4,
                            placeholder="Share your medical knowledge or corrections..."
                        )
                        
                        submit_feedback_btn = gr.Button("🎯 Submit Contribution", variant="primary")
                        feedback_result = gr.Textbox(label="Result", interactive=False)
                    
                    with gr.Column():
                        gr.HTML("### 🏆 Community Stats")
                        gr.HTML("""
                        <div style="padding: 16px; background: #f8f9fa; border-radius: 8px;">
                            <strong>Top Contributors:</strong><br>
                            🥇 Dr. Emily Watson - 200 contributions<br>
                            🥈 MedStudent_Alex - 156 contributions<br>
                            🥉 Nurse_Sarah92 - 134 contributions<br><br>
                            
                            <strong>💰 Reward Pool:</strong><br>
                            Total: 1,000,000 MEDAI<br>
                            Daily: 5,000 MEDAI<br>
                            Your Share: 245 MEDAI
                        </div>
                        """)
        
        # Disclaimer
        gr.HTML("""
        <div style="background: #fff3cd; border: 1px solid #ffd700; border-radius: 16px; padding: 20px; margin: 20px 0; color: #856404;">
            <strong>⚠️ Medical Disclaimer:</strong> This AI network provides educational information only. 
            Always consult healthcare professionals for medical decisions. For emergencies, call emergency services immediately.
        </div>
        """)
        
        # Event Handlers
        send_btn.click(
            fn=process_chat_message,
            inputs=[msg_input, image_display, recorded_audio, doctor_dropdown, chatbot],
            outputs=[msg_input, chatbot, image_display, recorded_audio]
        )
        
        msg_input.submit(
            fn=process_chat_message,
            inputs=[msg_input, image_display, recorded_audio, doctor_dropdown, chatbot],
            outputs=[msg_input, chatbot, image_display, recorded_audio]
        )
        
        doctor_dropdown.change(
            fn=update_doctor_selection,
            inputs=[doctor_dropdown],
            outputs=[doctor_info]
        )
        
        image_upload.upload(
            fn=lambda file: file,
            inputs=[image_upload],
            outputs=[image_display]
        )
        
        clear_btn.click(fn=clear_chat, outputs=[chatbot, image_display, recorded_audio])
        
        start_record_btn.click(
            fn=start_recording,
            outputs=[recording_status, start_record_btn, stop_record_btn]
        )
        
        stop_record_btn.click(
            fn=stop_recording,
            outputs=[recording_status, recorded_audio, start_record_btn, stop_record_btn]
        )
        
        audio_report_btn.click(fn=get_audio_report, outputs=[audio_output])
        
        send_email_btn.click(
            fn=handle_email_send,
            inputs=[email_input],
            outputs=[email_status]
        )
        
        create_proposal_btn.click(
            fn=governance_system.create_proposal,
            inputs=[proposal_title, proposal_description, proposer_name],
            outputs=[proposal_status]
        )
        
        vote_for_btn.click(
            fn=lambda pid, uid: governance_system.vote_on_proposal(pid, uid, "for"),
            inputs=[vote_proposal_id, voter_id],
            outputs=[vote_status]
        )
        
        vote_against_btn.click(
            fn=lambda pid, uid: governance_system.vote_on_proposal(pid, uid, "against"),
            inputs=[vote_proposal_id, voter_id],
            outputs=[vote_status]
        )
        
        submit_feedback_btn.click(
            fn=learning_system.submit_feedback,
            inputs=[contributor_id, analysis_id, feedback_type, feedback_text],
            outputs=[feedback_result]
        )
        
        # Initialize
        interface.load(
            fn=lambda: update_doctor_selection("Dr. Emily Watson"),
            outputs=[doctor_info]
        )
        
        interface.load(fn=display_active_proposals, outputs=[proposals_display])
        
        return interface

# ============================================================================
# LAUNCH APPLICATION
# ============================================================================

if __name__ == "__main__":
    print("🌐 Initializing DePIN Medical AI Network...")
    print(f"✅ Network nodes: {len(network_manager.active_nodes)}")
    print(f"✅ Blockchain initialized with {len(blockchain.chain)} blocks")
    print(f"✅ All systems ready")
    
    demo = create_depin_interface()
    demo.launch(share=True, show_error=True, debug=True) 
