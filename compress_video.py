import ffmpeg
import subprocess
from tqdm import tqdm
import cv2

def get_video_params(video):
    """ Get video parameters of interest, it can be modified as needed

    Args:
        video (str): path to video (e.g. 'path/to/video.mp4')

    Returns:
        Adjusted params: duration, nb_frames, size
    """

    probe = ffmpeg.probe(video)
    duration = float(probe['format']['duration'])
    nb_frames = int(probe["streams"][0]["nb_frames"])
    size = int(probe['format']['size'])
    return duration, nb_frames, size

def get_roi_to_crop(video_path):
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    
    # Read the first frame
    ret, frame = cap.read()
    if not ret:
        print("Failed to read the first frame.")
        return None

    # Display the first frame and let the user select the ROI
    roi = cv2.selectROI("Select ROI", frame, showCrosshair=True)
    cv2.destroyAllWindows()
    
    cap.release()

    # roi is a tuple of (x, y, width, height)
    return roi

def compress_video(
    input_file_path, 
    output_file_path, 
    fps=25, 
    seconds_to_cut=0, 
    video_resolution="low", 
    overwrite=True, 
    remove_audio=True, 
    crop_video=True
):
    
    """ Use video codec (encoder - decoder) to reduce file size

    Args:
        input_file_path (str): path to the original video
        output_file_path (str): path destination
        fps (int): fps of the output video
        seconds_to_cut (float): seconds to be removed at the end of the video
        video_resolution ("low", "medium", "high"): quality of the output video, 480, 720, 1080 respectively
        overwrite (bool): existing output file is replaced if True
    """

    duration, frames, ip_size = get_video_params(input_file_path)
    new_duration = duration - seconds_to_cut

    match(video_resolution):
        case("low"):
            video_resolution = 480
        case("medium"):
            video_resolution = 720
        case("high"):
            video_resolution = 1080

    single_cmd = []
    if crop_video:
        x, y, w, h = get_roi_to_crop(input_file_path)
        single_cmd = ('-vf', f'crop={w}:{h}:{x}:{y}')

    # x, y, w, h = get_roi_to_crop(input_file_path) if crop_video else x, y, w, h = 0, 0, 0, 0
    #'-vf', f'crop={w}:{h}:{x}:{y}'

    cmd = [
        'ffmpeg', '-i', input_file_path, 
        '-t', str(new_duration),
        '-vf', f'fps={fps},scale={video_resolution}:-1',  # Adjust FPS and scale
        '-c:v', 'libx265',  # Set codec to libx265 for compression
        *single_cmd,
        *(['-an'] if remove_audio else ['-c:a', 'copy']), # Remove audio from video -> ~64% size reduction
        '-y' if overwrite else 'n',  # Overwrite output file if it exists
        output_file_path
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    pbar = tqdm(total=duration, unit='s', desc="Processing Video", ncols=100)

    # Monitor the stderr (progress)
    for line in process.stderr:
        if "time=" in line:
            # Extract the current timestamp (time=HH:MM:SS.xxx)
            time_str = line.split('time=')[1].split(' ')[0]
            hours, minutes, seconds = map(float, time_str.split(':'))
            current_time = hours * 3600 + minutes * 60 + seconds
            pbar.update(current_time - pbar.n)  # Update progress bar

    # Wait for the FFmpeg process to finish
    process.communicate()
    
    # Ensure the progress bar is fully flushed before the next print
    pbar.update(duration - pbar.n)  # Ensure the bar reaches 100%
    pbar.close()

    duration, frames, op_size = get_video_params(output_file_path)
    diff_size = (ip_size - op_size)
    print(f"\nVideo processed! {diff_size/ip_size*100: .3f}% compressed ({diff_size/1024: .3f} kb less)!")
