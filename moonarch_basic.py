from spleeter.separator import Separator
import os

class BasicSplitter:
    def __init__(self, input_path, task='spleeter:4stems'):
        self.input_path = input_path
        self.task = task
        self.separator = Separator(self.task)
    
    def separate_audio(self):
        output_path = os.getcwd()  # Use current directory as output path
        
        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)
        
        # Perform the separation
        self.separator.separate_to_file(self.input_path, output_path)
        
    def run(self):
        # Perform the separation
        self.separate_audio()
        
        print("Separation completed")

# Example usage
#splitter = AdvanceSplitter('SS.mp3')
#splitter.run()
