import os
import subprocess
import time
import sys

# --- CONFIGURATION ---
TARGET_RES = "1920:1080" 
OUTPUT_BASE = os.path.dirname(os.getcwd()) 
OUTPUT_FOLDER = os.path.join(OUTPUT_BASE, "1080p")
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.ts')

def get_ffmpeg_command():
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    return "ffmpeg"

def convert_videos():
    ffmpeg_cmd = get_ffmpeg_command()
    print(f"Engine: {ffmpeg_cmd}")

    if not os.path.exists(OUTPUT_FOLDER):
        try:
            os.makedirs(OUTPUT_FOLDER)
        except PermissionError:
            return

    files = [f for f in os.listdir('.') if f.lower().endswith(VIDEO_EXTENSIONS)]
    print(f"Found {len(files)} videos. Starting Optimized Conversion...")

    for i, filename in enumerate(files):
        output_name = os.path.join(OUTPUT_FOLDER, filename)
        print(f"[{i+1}/{len(files)}] Processing: {filename}")
        
        # --- STRATEGY 1: FULL GPU (Decoder + VPP Scaler + Encoder) ---
        # We replaced 'scale_qsv' with 'vpp_qsv' which is newer and less buggy.
        cmd_full_gpu = [
            ffmpeg_cmd, '-y',
            '-hwaccel', 'qsv',
            '-hwaccel_output_format', 'qsv',
            '-i', filename,
            '-vf', f'vpp_qsv=w={TARGET_RES.split(":")[0]}:h={TARGET_RES.split(":")[1]}', 
            '-c:v', 'h264_qsv',
            '-preset', 'veryfast',
            '-b:v', '4500k',
            '-map_metadata', '0',
            '-movflags', 'use_metadata_tags',
            '-c:a', 'copy',
            output_name
        ]
        
        # --- STRATEGY 2: BALANCED (Hardware Decode + CPU Resize + GPU Encode) ---
        # Uses -hwaccel auto to decode (Saves CPU) -> CPU Resizes (Compatible) -> GPU Encodes (Fast)
        cmd_balanced = [
            ffmpeg_cmd, '-y',
            '-hwaccel', 'auto',       # <--- CRITICAL: Uses GPU to READ the file
            '-i', filename,
            '-vf', f'scale={TARGET_RES.split(":")[0]}:h={TARGET_RES.split(":")[1]}', # Standard CPU Scaler
            '-c:v', 'h264_qsv',       # Hardware Encoder
            '-preset', 'veryfast',
            '-b:v', '4500k',
            '-map_metadata', '0',
            '-movflags', 'use_metadata_tags',
            '-c:a', 'copy',
            output_name
        ]

        try:
            start_time = time.time()
            # Attempt 1: Try the new VPP Scaler
            print("  > Attempting Full GPU pipeline (vpp_qsv)...")
            subprocess.run(cmd_full_gpu, check=True, stderr=subprocess.DEVNULL)
            print(f"  > Success (Full GPU)! Done in {time.time() - start_time:.1f}s")
            
        except subprocess.CalledProcessError:
            print("  > Full GPU failed. Switching to Balanced Mode (Hardware Decode)...")
            try:
                # Attempt 2: The Low-CPU Hybrid Method
                start_time = time.time()
                subprocess.run(cmd_balanced, check=True)
                print(f"  > Success (Balanced). Done in {time.time() - start_time:.1f}s")
            except subprocess.CalledProcessError:
                 # Attempt 3: Absolute Fail-safe (Slowest)
                print("  > Balanced failed. Using slow CPU fallback.")
                subprocess.run([ffmpeg_cmd, '-y', '-i', filename, '-vf', f'scale={TARGET_RES.split(":")[0]}:h={TARGET_RES.split(":")[1]}', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'copy', output_name])

if __name__ == "__main__":
    convert_videos()

