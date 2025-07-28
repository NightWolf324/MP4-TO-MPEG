import subprocess
import os
import sys
import time
import shutil
import tempfile
import logging
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("conversion_errors.log"),
        logging.StreamHandler()
    ]
)

def get_ffmpeg_path():
    """Get FFmpeg path with fallbacks"""
    # Try common paths
    paths = [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"
    ]
    
    for path in paths:
        if shutil.which(path) or os.path.exists(path):
            return path
    
    logging.error("FFmpeg tidak ditemukan! Silakan instal FFmpeg terlebih dahulu.")
    logging.info("Download dari: https://github.com/BtbN/FFmpeg-Builds/releases")
    logging.info("Ekstrak ke C:\\ffmpeg dan tambahkan ke PATH")
    return None

def convert_file(ffmpeg_path, input_path, output_path):
    """Convert single file with optimized compression for old Android devices"""
    try:
        # Create temp directory with short path
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Copy to temp location with short name
            tmp_input = os.path.join(tmp_dir, "input.mp4")
            shutil.copy2(input_path, tmp_input)
            
            # Run FFmpeg conversion with optimized settings
            command = [
                ffmpeg_path,
                '-i', tmp_input,
                
                # Optimized video settings for MPEG
                '-c:v', 'mpeg2video',    # Codec video MPEG-2
                '-b:v', '600k',          # Bitrate video target
                '-maxrate', '800k',      # Bitrate maksimum
                '-bufsize', '1200k',     # Buffer size
                '-g', '15',              # GOP size lebih pendek
                '-bf', '0',              # Nonaktifkan B-frames
                '-vf', 'scale=640:360',  # Resolusi 360p (640x360)
                '-r', '24',              # Frame rate 24fps
                
                # Optimized audio settings
                '-c:a', 'mp2',           # Codec audio MP2
                '-b:a', '48k',           # Bitrate audio
                '-ar', '32000',          # Sample rate
                '-ac', '1',              # Mono audio
                
                # Additional optimizations
                '-threads', '0',         # Gunakan semua thread CPU
                '-f', 'mpeg',            # Format output MPEG
                os.path.join(tmp_dir, "output.mpeg")  # Format MPEG
            ]
            
            # Run and capture output
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=600  # 10 minutes timeout
            )
            
            # Check result
            if result.returncode == 0:
                # Copy converted file to final destination
                shutil.copy2(os.path.join(tmp_dir, "output.mpeg"), output_path)
                
                # Dapatkan ukuran file untuk logging
                input_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
                output_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                compression_ratio = (1 - (output_size / input_size)) * 100
                
                return True, f"Ukuran: {output_size:.2f}MB (Kompresi: {compression_ratio:.1f}%)"
            else:
                # Extract error message
                error_lines = result.stderr.split('\n')
                error_msg = ""
                for line in error_lines:
                    if "error" in line.lower() or "failed" in line.lower():
                        error_msg = line.strip()
                        break
                if not error_msg:
                    error_msg = result.stderr[-500:] or "Unknown error"
                return False, error_msg
                
    except Exception as e:
        return False, str(e)

def sanitize_filename(filename):
    """Remove problematic characters from filename"""
    # Remove invalid characters
    clean = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Shorten if too long
    return clean[:150] if len(clean) > 150 else clean

def convert_folder(input_folder, output_folder=None):
    """Convert all MP4 files in a folder to MPEG"""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return
    
    # Tentukan folder output
    if output_folder is None:
        output_folder = os.path.join(input_folder, "MPEG_360p_Output")  # Default
    
    os.makedirs(output_folder, exist_ok=True)
    
    # Collect MP4 files
    mp4_files = []
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith('.mp4'):
                full_path = os.path.join(root, file)
                mp4_files.append(full_path)
    
    if not mp4_files:
        logging.warning("Tidak ada file MP4 di folder ini")
        return
    
    total_files = len(mp4_files)
    logging.info(f"Ditemukan {total_files} file MP4 untuk dikonversi")
    
    # Convert files
    success_count = 0
    start_time = time.time()
    
    for i, input_path in enumerate(mp4_files, 1):
        filename = os.path.basename(input_path)
        safe_name = sanitize_filename(filename)
        output_path = os.path.join(output_folder, os.path.splitext(safe_name)[0] + ".mpeg")  # Ekstensi .mpeg
        
        logging.info(f"[{i}/{total_files}] Mengkonversi: {filename}")
        
        # Skip jika file output sudah ada dan lebih baru
        if os.path.exists(output_path) and os.path.getmtime(output_path) > os.path.getmtime(input_path):
            logging.info(f"⏩ Dilewati: {filename} (sudah dikonversi)")
            success_count += 1
            continue
        
        success, result_msg = convert_file(ffmpeg_path, input_path, output_path)
        
        if success:
            success_count += 1
            logging.info(f"✅ Berhasil: {filename} - {result_msg}")
        else:
            logging.error(f"❌ Gagal: {filename}")
            logging.error(f"   Penyebab: {result_msg}")
    
    # Generate report
    elapsed = time.time() - start_time
    mins, secs = divmod(elapsed, 60)
    
    logging.info("\n" + "=" * 60)
    logging.info("LAPORAN KONVERSI:")
    logging.info(f"Total file: {total_files}")
    logging.info(f"Berhasil: {success_count}")
    logging.info(f"Gagal: {total_files - success_count}")
    logging.info(f"Waktu: {int(mins)} menit {int(secs)} detik")
    
    # Hitung penghematan ruang
    if success_count > 0:
        total_input_size = 0
        total_output_size = 0
        
        for input_path in mp4_files:
            if os.path.exists(input_path):
                total_input_size += os.path.getsize(input_path)
        
        for file in os.listdir(output_folder):
            if file.endswith(".mpeg"):
                output_path = os.path.join(output_folder, file)
                total_output_size += os.path.getsize(output_path)
        
        total_input_mb = total_input_size / (1024 * 1024)
        total_output_mb = total_output_size / (1024 * 1024)
        savings = total_input_mb - total_output_mb
        savings_percent = (savings / total_input_mb) * 100 if total_input_mb > 0 else 0
        
        logging.info(f"Total ukuran input: {total_input_mb:.2f} MB")
        logging.info(f"Total ukuran output: {total_output_mb:.2f} MB")
        logging.info(f"Penghematan ruang: {savings:.2f} MB ({savings_percent:.1f}%)")
    
    logging.info(f"Output disimpan di: {output_folder}")
    logging.info("=" * 60)
    
    # Save failed files list
    if success_count < total_files:
        with open(os.path.join(output_folder, "failed_files.txt"), "w", encoding="utf-8") as f:
            f.write("File yang gagal dikonversi:\n")
            for i, input_path in enumerate(mp4_files, 1):
                filename = os.path.basename(input_path)
                output_path = os.path.join(output_folder, os.path.splitext(sanitize_filename(filename))[0] + ".mpeg")
                if not os.path.exists(output_path):
                    f.write(f"{i}. {filename}\n")

def main():
    print("=" * 60)
    print("KONVERTER MP4 KE MPEG (360p)")
    print("=" * 60)
    print("Pengaturan kompresi yang digunakan:")
    print("- Format: MPEG (ekstensi .mpeg)")
    print("- Resolusi: 640x360 (360p)")
    print("- Frame rate: 24fps")
    print("- Video: MPEG2, 600kbps bitrate")
    print("- Audio: Mono, 48k bitrate, 32kHz sample rate")
    
    # Ambil folder input
    if len(sys.argv) > 1:
        input_folder = sys.argv[1]
    else:
        input_folder = input("\nMasukkan folder INPUT: ").strip()
    
    # Handle drag & drop quotes
    if input_folder.startswith('"') and input_folder.endswith('"'):
        input_folder = input_folder[1:-1]
    
    # Ambil folder output
    output_folder = None
    if len(sys.argv) > 2:
        output_folder = sys.argv[2]
    else:
        output_folder_input = input("\nMasukkan folder OUTPUT (kosongkan untuk default): ").strip()
        if output_folder_input:
            if output_folder_input.startswith('"') and output_folder_input.endswith('"'):
                output_folder = output_folder_input[1:-1]
            else:
                output_folder = output_folder_input
    
    if not os.path.isdir(input_folder):
        logging.error(f"Folder input tidak valid: {input_folder}")
        return
    
    # Jalankan konversi
    convert_folder(input_folder, output_folder)
    
    if os.name == 'nt':
        input("\nTekan Enter untuk keluar...")

if __name__ == "__main__":
    main()