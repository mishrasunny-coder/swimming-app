#!/usr/bin/env python3
"""
Launcher script for the Swimming Results Database
"""
import subprocess
import sys
import os

def main():
    """Run the swimming results Streamlit app"""
    
    # Check if we're in the right directory
    if not os.path.exists("swimming_results_app.py"):
        print("❌ Error: swimming_results_app.py not found!")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    # Check if CSV files exist
    csv_files = [
        "25_Yard_Freestyle.csv",
        "25_Yard_Breaststroke.csv", 
        "25_Yard_Backstroke.csv",
        "25_Yard_Butterfly.csv"
    ]
    
    missing_files = [f for f in csv_files if not os.path.exists(f)]
    if missing_files:
        print(f"⚠️  Warning: Missing CSV files: {missing_files}")
        print("The app will still run but may not have all data.")
    
    print("🏊‍♀️ Starting Swimming Results Database...")
    print("📊 Loading swimming data from CSV files...")
    print("🌐 Opening web interface...")
    print("")
    print("The app will open in your default browser.")
    print("If it doesn't open automatically, go to: http://localhost:8501")
    print("")
    print("Press Ctrl+C to stop the application.")
    print("-" * 50)
    
    try:
        # Run streamlit app
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "swimming_results_app.py",
            "--server.port", "8501",
            "--server.address", "localhost"
        ])
    except KeyboardInterrupt:
        print("\n👋 Swimming Results Database stopped.")
    except Exception as e:
        print(f"❌ Error running the app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
