import subprocess
from pathlib import Path
import tempfile
import json

VIDEO_EXTENSION = '.mp4'

def run(args: list):
  str_args = [str(arg) for arg in args]
  print('Running command:', ' '.join(str_args))
  output = subprocess.check_output(str_args)
  print(output.decode('utf-8'))

def check_executable(name: str):
  try:
    subprocess.run([name, '-version'])
  except FileNotFoundError:
    print(f'{name} not found. Please install {name}.')
    exit(1)

def get_video_duration(input_file: Path) -> float:
  output = subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', input_file])
  data = json.loads(output)
  return float(data['format']['duration'])

def get_media_dimensions(media_file: Path) -> tuple:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', str(media_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    width, height = map(int, result.stdout.strip().split('x'))
    return width, height

def process_video(input_file: Path, background_image_path: Path, output_file: Path):
  duration = get_video_duration(input_file) - 1
  temp_file1 = Path(tempfile.mktemp(VIDEO_EXTENSION))
  temp_file2 = Path(tempfile.mktemp(VIDEO_EXTENSION))
  # Processes:
  # 1. Flip the video horizontally
  # 2. Remove audio
  # 3. Remove first 0.5 seconds and last 0.5 seconds
  run(['ffmpeg', '-i', input_file, '-vf', 'hflip', '-an', '-ss', '0.5', '-t', duration, temp_file1])
  
  # Get dimensions of the background image and the video
  bg_width, bg_height = get_media_dimensions(background_image_path)
  video_width, video_height = get_media_dimensions(temp_file1)
  print('Background image dimensions:', bg_width, bg_height)
  print('Video dimensions:', video_width, video_height)

  # Calculate the scale and offset to center the video on the background image
  video_ratio = video_width / video_height
  bg_ratio = bg_width / bg_height
  if video_ratio > bg_ratio:
      # Video is wider than the background image
      scaled_bg_width = video_width
      scaled_bg_height = int(video_width / bg_ratio)
      x_offset = 0
      y_offset = (scaled_bg_height - video_height) // 2
  else:
      # Video is taller than the background image
      scaled_bg_height = video_height
      scaled_bg_width = int(video_height * bg_ratio)
      x_offset = (scaled_bg_width - video_width) // 2
      y_offset = 0

  print('Scaled background image dimensions:', scaled_bg_width, scaled_bg_height)

  # Ensure dimensions are divisible by 2
  scaled_bg_width = scaled_bg_width if scaled_bg_width % 2 == 0 else scaled_bg_width + 1
  scaled_bg_height = scaled_bg_height if scaled_bg_height % 2 == 0 else scaled_bg_height + 1
  video_width = video_width if video_width % 2 == 0 else video_width + 1
  video_height = video_height if video_height % 2 == 0 else video_height + 1

  # 4. Add video on top of the background image
  run([
      'ffmpeg', '-i', background_image_path, '-i', temp_file1,
      '-filter_complex', f'[0:v]scale={scaled_bg_width}:{scaled_bg_height}[bg];[1:v]scale={video_width}:{video_height}[video];[bg][video]overlay={x_offset}:{y_offset}',
      '-c:a', 'copy', temp_file2
  ])

  # Rename the temp file to the output file
  output_file.unlink(missing_ok=True)
  temp_file2.rename(output_file)

def main(input_folder: Path, background_image_path: Path, output_folder: Path, force: bool, verbose: bool):
  # Check ffmpeg and ffprobe
  check_executable('ffmpeg')
  check_executable('ffprobe')
  # Create output folder
  output_folder.mkdir(exist_ok=True, parents=True)
  # Traverse the input folder
  skipped_files = []
  processed_files = []
  for input_file in input_folder.glob(f'*{VIDEO_EXTENSION}'):
    output_file = output_folder / input_file.name
    if not force and output_file.exists():
      skipped_files.append(input_file)
      continue
    process_video(input_file, background_image_path, output_file)
    processed_files.append(input_file)
  # Print summary
  print('Summary:')
  print('Processed files:', len(processed_files))
  if verbose:
    for file in processed_files:
      print(f'  {file.name}')
  print('Skipped files:', len(skipped_files))

if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('-i', '--input-folder', type=Path, required=True, help='folder containing videos to process')
  parser.add_argument('-b', '--background-image-path', type=Path, required=True, help='path to the background image')
  parser.add_argument('-o', '--output-folder', type=Path, required=True, help='folder to save the processed videos')
  parser.add_argument('-f', '--force', action='store_true', help='force reprocessing of existing videos')
  parser.add_argument('-v', '--verbose', action='store_true', help='print verbose output')
  args = parser.parse_args()
  main(args.input_folder, args.background_image_path, args.output_folder, args.force, args.verbose)
