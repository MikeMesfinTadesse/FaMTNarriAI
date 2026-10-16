"""
ml/train.py — MLflow experiment tracking for FaMTNarriAI
Tracks TTS conversion parameters and metrics
"""
import mlflow
import mlflow.sklearn
import time
import os

# Set tracking URI — stores experiments locally
mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("famtnarriai-tts")

def simulate_tts_conversion(voice, speed, text_length):
    """Simulate a TTS conversion and track it with MLflow"""
    
    with mlflow.start_run():
        # Log parameters
        mlflow.log_param("voice", voice)
        mlflow.log_param("speed", speed)
        mlflow.log_param("text_length", text_length)
        mlflow.log_param("engine", "edge-tts")
        
        # Simulate conversion
        start = time.time()
        time.sleep(0.1)  # simulate processing
        duration = time.time() - start
        
        # Simulate metrics
        estimated_audio_duration = (text_length / 150) * 60 / speed  # seconds
        chars_per_second = text_length / duration
        
        # Log metrics
        mlflow.log_metric("processing_time_seconds", round(duration, 3))
        mlflow.log_metric("estimated_audio_duration", round(estimated_audio_duration, 1))
        mlflow.log_metric("chars_per_second", round(chars_per_second, 0))
        mlflow.log_metric("text_length", text_length)
        
        print(f"✅ Run tracked: voice={voice}, speed={speed}, text_length={text_length}")
        print(f"   Processing time: {duration:.3f}s")
        print(f"   Estimated audio: {estimated_audio_duration:.1f}s")
        
        return estimated_audio_duration

if __name__ == "__main__":
    print("🎙 FaMTNarriAI — MLflow Experiment Tracking\n")
    
    # Run multiple experiments with different parameters
    experiments = [
        ("en-US-AriaNeural",   1.0, 500),
        ("en-US-JennyNeural",  0.9, 1000),
        ("en-GB-RyanNeural",   1.1, 250),
        ("ar-SA-ZariyahNeural",1.0, 800),
        ("am-ET-MekdesNeural", 0.85,600),
    ]
    
    for voice, speed, length in experiments:
        simulate_tts_conversion(voice, speed, length)
    
    print("\n✅ All runs tracked. Open MLflow UI:")
    print("   mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000")
    print("   Then open http://localhost:5000")
