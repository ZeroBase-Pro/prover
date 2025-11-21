import ujson
import logging
import threading

class ProjectManager:
    """
    Singleton manager for project configurations.
    
    Loads project information from a JSON file and provides methods
    to retrieve project details by project ID.
    """
    _instance = None
    _locker = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Create singleton instance."""
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(ProjectManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_path):
        """
        Initialize ProjectManager.
        
        :param project_path: Path to the JSON file containing project configurations
        """
        if self._initialized:
            return

        self.project_path = project_path
        self.projects = {}
        self._load_projects()
        self._initialized = True

    def _load_projects(self):
        """Load project configurations from JSON file."""
        try:
            with open(self.project_path, 'r') as file:
                self.projects = ujson.load(file)
            logging.info("Projects loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load projects: {e}")
            self.projects = {}



    def get_project(self, project_id):
        """Retrieve details of a specific project based on project_id."""
        # Check if the project_id length is 5 digits
        if len(str(project_id)) == 5:
            # Directly match project in the projects dictionary
            return self.projects.get(str(project_id), {"project_name": "Anonymous", "verifiers": ["Unknow"]})
        else:
            # If the project_id length is not 5, process it by splitting
            if len(str(project_id)) % 2 != 0:
                logging.warning(f"Project ID length is odd, unable to split correctly.")
                return {"project_name": "Anonymous", "verifiers": ["Unknow"]}
            
            # Split the project_id into chunks of 2 characters each
            clean_id = ""
            for i in range(0, len(str(project_id)), 2):
                chunk = str(project_id)[i:i+2]
                try:
                    char = int(chr(int(chunk)))
                except Exception as e:
                    continue
                char = str(char)  # Convert the 2-character hex to character
                clean_id += char
            return self.projects.get(clean_id, {"project_name": "Anonymous", "verifiers": ["Unknow"]})
