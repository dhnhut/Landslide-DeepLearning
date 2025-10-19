import ee
import os

def initialize_ee(ipython_instance):
    if 'google.colab' in str(ipython_instance):
        from google.colab import userdata
        EE_PROJECT_ID = userdata.get('EE_PROJECT_ID') 
    else:
        from dotenv import load_dotenv
        load_dotenv()  # take environment variables
        EE_PROJECT_ID = os.getenv('EE_PROJECT_ID')

    # Set up GEE API
    ee.Authenticate()
    ee.Initialize(project=EE_PROJECT_ID) #<- Remember to change this to your own project's name!
    return ee