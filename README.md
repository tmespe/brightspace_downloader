# Brightspace_downloader
Downloads course contents from a list of brightspace courses and course codes and saves to users documents folder 
or a specified folder. 

# Requirements
- python = "^3.8"
- selenium = "^3.141.0"
- python-dotenv = "^0.19.0"

Install requirements and add a .env file to the root folder with USER_NAME and PASSWORD for brightspace username 
and password. 

Download and install geckodriver for your OS and make sure it's in PATH. 

# Instructions
To run use python3 main.py to download to your users documents folder. Use python3 main.py -d **folder path** to 
download to the specified folder.  
