import sys
import os
import json
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QCompleter, QLineEdit, QPushButton, QFileDialog, QLabel, QTextEdit, QMessageBox, QProgressBar, QComboBox, QFormLayout, QHBoxLayout
)
from PyQt5.QtCore import Qt

button_name_mapping = {
    # Power
    r"power": "Power",
    r"pwr": "Power",
    # Volume Up
    r"vol(?:_)?up": "Vol_up",
    r"volume(?:_)?up": "Vol_up",
    r"vol(?:_)?increase": "Vol_up",
    r"vol(?:_)?inc": "Vol_up",
    r"vol(?:_)?\+": "Vol_up",
    # Volume Down
    r"vol(?:_)?down": "Vol_dn",
    r"volume(?:_)?down": "Vol_dn",
    r"vol(?:_)?decrease": "Vol_dn",
    r"vol(?:_)?dec": "Vol_dn",
    r"vol(?:_)?\-": "Vol_dn",
    r"vol(?:_)?dwn": "Vol_dn",
    # Channel Up
    r"ch(?:_)?up": "Ch_next",
    r"channel(?:_)?up": "Ch_next",
    r"chan(?:_)?up": "Ch_next",
    r"ch(?:_)?next": "Ch_next",
    r"channel(?:_)?next": "Ch_next",
    # Channel Down
    r"ch(?:_)?down": "Ch_prev",
    r"channel(?:_)?down": "Ch_prev",
    r"chan(?:_)?down": "Ch_prev",
    r"ch(?:_)?prev": "Ch_prev",
    r"channel(?:_)?prev": "Ch_prev",
    # Mute
    r"mute": "Mute",
    r"silence": "Mute",
    r"mte": "Mute",
    # Play
    r"play": "Play",
    r"pl": "Play",
    # Pause
    r"pause": "Pause",
    r"hold": "Pause",
    # Next
    r"next": "Next",
    r"skip(?:_)?fwd": "Next",
    r"forward": "Next",
    r"fwd": "Next",
    # Previous
    r"prev(?:ious)?": "Prev",
    r"skip(?:_)?back": "Prev",
    r"back": "Prev",
    r"rewind": "Prev",
    r"rwd": "Prev",
    # Power Off
    r"off": "Off",
    r"shutdown": "Off",
    r"shut(?:_)?down": "Off",
    # Air Conditioner Modes
    r"cool(?:_)?hi": "Cool_hi",
    r"cool(?:_)?lo": "Cool_lo",
    r"heat(?:_)?hi": "Heat_hi",
    r"heat(?:_)?lo": "Heat_lo",
    # Dehumidifier Mode
    r"dh": "Dh",
    r"dehumidify": "Dh",
    r"dry": "Dh"
}

class IRFileFormatter(QWidget):
    def __init__(self):
        super().__init__()
        self.user_preferences = self.load_preferences()
        self.init_ui()

    # List of common brands
    brands = [
        "Samsung", "Sony", "LG", "Panasonic", "Philips", "Sharp", "Toshiba", "Vizio", 
        "Hisense", "Mitsubishi", "RCA", "Sanyo", "Pioneer", "JVC", "Denon", "Yamaha", 
        "Onkyo", "Bose", "Harman Kardon", "Polk Audio", "Marantz", "Nakamichi", "Apple", 
        "Google", "Amazon", "Microsoft", "PlayStation", "Xbox", "Nintendo", "Canon", 
        "Nikon", "Fujifilm", "Olympus", "Leica", "Logitech", "Huawei", "HTC", "Motorola", 
        "OnePlus", "Xiaomi", "Oppo", "Realme", "Tecno", "Vivo", "Bang & Olufsen", "Bowers & Wilkins", 
        "Sennheiser", "Klipsch", "Sonos", "JBL", "Harman/Kardon", "Marshall", "Polaroid", 
        "Casio", "Kodak", "Garmin", "GoPro", "Fitbit", "Ring", "Nest", "Wyze", "TP-Link", 
        "Linksys", "Netgear", "Belkin", "Asus", "Acer", "Dell", "HP", "Lenovo", "IBM", 
        "Alienware", "Razer", "Corsair", "Cooler Master", "MSI", "Gigabyte", "Zotac", 
        "EVGA", "Thermaltake", "Antec", "Fractal Design", "SilverStone", "Behringer", 
        "Roland", "Korg", "Yamaha", "Casio", "Alesis", "Nord", "Moog", "Akai", "Numark", 
        "DJI", "Parrot", "Yuneec", "Sky Viper", "Holy Stone", "Syma", "Hubsan", "Autel", 
        "3DR", "iRobot", "Ecovacs", "Neato", "Roborock", "Dyson", "Shark", "Miele", 
        "Bissell", "Eureka", "Hoover", "Black+Decker", "KitchenAid", "Cuisinart", "Breville", 
        "Nespresso", "Keurig", "Smeg", "Vitamix", "Blendtec", "Ninja", "Instant Pot", 
        "Crock-Pot", "Frigidaire", "GE", "Whirlpool", "Maytag", "Bosch", "Miele", "Dyson", 
        "Kenmore", "Electrolux", "Amana", "Haier", "Daewoo", "TCL", "Insignia", "Element", 
        "Westinghouse", "Magnavox", "Sceptre", "Hisense", "Hitachi", "Jensen", "Emerson", 
        "Roku", "Fire TV", "Chromecast", "Apple TV"
    ]

    
    def init_ui(self):
        self.setWindowTitle("IR File Formatter")
        self.setGeometry(300, 300, 400, 600)

        # Main layout
        main_layout = QVBoxLayout()

        # Instructions
        self.instructions_label = QLabel("Step 1: Select the .ir file you want to format:")
        main_layout.addWidget(self.instructions_label)

        # File selection
        file_layout = QHBoxLayout()
        self.file_path_input = QLineEdit(self)
        file_layout.addWidget(self.file_path_input)
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse_files)
        file_layout.addWidget(self.browse_button)
        main_layout.addLayout(file_layout)

        # Device type
        self.device_type_label = QLabel("Step 2: Select the device type:")
        main_layout.addWidget(self.device_type_label)
        self.device_type_combo = QComboBox(self)
        self.device_type_combo.addItems([
            "TV", "Audio", "AC", "DVD Player", "Projector", 
            "Set-Top Box", "Fan", "Lights", "Gaming Console", 
            "Soundbar", "Blu-ray Player", "Satellite Receiver", 
            "Home Theater", "Camera", "Smart Home", "Other"
        ])
        main_layout.addWidget(self.device_type_combo)

        # Save directory selection
        self.save_dir_label = QLabel("Step 3: Select the save directory:")
        main_layout.addWidget(self.save_dir_label)
        save_dir_layout = QHBoxLayout()
        self.save_dir_input = QLineEdit(self)
        save_dir_layout.addWidget(self.save_dir_input)
        self.browse_save_dir_button = QPushButton("Browse", self)
        self.browse_save_dir_button.clicked.connect(self.browse_save_directory)
        save_dir_layout.addWidget(self.browse_save_dir_button)
        main_layout.addLayout(save_dir_layout)

        # Form for brand, remote model, and device model
        form_layout = QFormLayout()
        self.brand_input = QLineEdit(self)
        self.brand_input.setPlaceholderText("E.g., Samsung")
        brand_completer = QCompleter(self.brands, self)
        self.brand_input.setCompleter(brand_completer)
        form_layout.addRow("Brand:", self.brand_input)

        self.remote_model_input = QLineEdit(self)
        self.remote_model_input.setPlaceholderText("E.g., AA59-00741A")
        form_layout.addRow("Remote Model:", self.remote_model_input)

        self.device_model_input = QLineEdit(self)
        self.device_model_input.setPlaceholderText("E.g., UN55NU7100 (optional)")
        form_layout.addRow("Device Model(s):", self.device_model_input)

        main_layout.addLayout(form_layout)

        # Process button and progress bar
        self.process_button = QPushButton("Step 4: Process File", self)
        self.process_button.clicked.connect(self.process_ir_file)
        main_layout.addWidget(self.process_button)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.progress_bar)

        # Output log
        self.output_text = QTextEdit(self)
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Processing logs will appear here...")
        main_layout.addWidget(self.output_text)

        self.setLayout(main_layout)

    def browse_files(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select .ir File", "", "IR Files (*.ir);;All Files (*)", options=options)
        if file_path:
            self.file_path_input.setText(file_path)

    def browse_save_directory(self):
        save_dir = QFileDialog.getExistingDirectory(self, "Select Save Directory", options=QFileDialog.ShowDirsOnly)
        if save_dir:
            self.save_dir_input.setText(save_dir)

    def load_preferences(self):
        if os.path.exists("user_preferences.json"):
            with open("user_preferences.json", "r") as file:
                return json.load(file)
        return {}

    def save_preferences(self):
        self.user_preferences["last_brand"] = self.brand_input.text()
        self.user_preferences["last_remote_model"] = self.remote_model_input.text()
        with open("user_preferences.json", "w") as file:
            json.dump(self.user_preferences, file)

    def normalize_button_name(self, button_name):
        cleaned_name = button_name.lower().replace(" ", "").replace("_", "").replace("-", "")
        for pattern, standard_name in button_name_mapping.items():
            if re.match(pattern, cleaned_name):
                return standard_name
        return button_name

    # Example usage during parsing
    def parse_ir_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Failed to read the file: {e}")
            return None

        ir_data = []
        current_button = {}
        for line in lines:
            line = line.strip()
            if line.startswith('name:'):
                if current_button:
                    ir_data.append(current_button)
                    current_button = {}
                user_button_name = line.split(': ')[1]
                normalized_name = self.normalize_button_name(user_button_name)
                current_button['name'] = normalized_name
            elif line.startswith('type:'):
                current_button['type'] = line.split(': ')[1]
            elif line.startswith('protocol:'):
                current_button['protocol'] = line.split(': ')[1]
            elif line.startswith('address:'):
                current_button['address'] = line.split(': ')[1]
            elif line.startswith('command:'):
                current_button['command'] = line.split(': ')[1]
            elif line.startswith('frequency:'):
                current_button['frequency'] = line.split(': ')[1]
            elif line.startswith('duty_cycle:'):
                current_button['duty_cycle'] = line.split(': ')[1]
            elif line.startswith('data:'):
                current_button['data'] = line.split(': ')[1]
        if current_button:
            ir_data.append(current_button)

        return ir_data

    def create_ir_content(self, brand, remote_model, device_model, ir_data):
        ir_content = "Filetype: IR signals file\nVersion: 1\n#\n"
        ir_content += f"# {brand} {remote_model} {device_model}\n#\n"

        for button in ir_data:
            ir_content += f"name: {button['name']}\n"
            ir_content += f"type: {button['type']}\n"
            if button['type'] == 'parsed':
                ir_content += f"protocol: {button['protocol']}\n"
                ir_content += f"address: {button['address']}\n"
                ir_content += f"command: {button['command']}\n"
            elif button['type'] == 'raw':
                ir_content += f"frequency: {button['frequency']}\n"
                ir_content += f"duty_cycle: {button['duty_cycle']}\n"
                ir_content += f"data: {button['data']}\n"
            ir_content += "#\n"

        return ir_content

    def save_ir_file(self, brand, remote_model, ir_content, original_filename):
        try:
            device_type = self.device_type_combo.currentText()
            save_dir = self.save_dir_input.text().strip()
            if not save_dir:
                save_dir = os.getcwd()  # Use the current working directory if no directory is specified
            
            directory = os.path.join(save_dir, device_type)
            os.makedirs(directory, exist_ok=True)

            filename = f"{brand}_{remote_model}.ir"
            file_path = os.path.join(directory, filename)

            with open(file_path, 'w') as f:
                f.write(ir_content)

            self.output_text.append(f"IR file saved as {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save the file: {e}")

    def process_ir_file(self):
        self.progress_bar.setValue(0)

        file_path = self.file_path_input.text().strip()
        brand = self.brand_input.text().strip()
        remote_model = self.remote_model_input.text().strip()
        device_model = self.device_model_input.text().strip()

        if not file_path or not os.path.isfile(file_path):
            QMessageBox.critical(self, "Error", "Please select a valid .ir file.")
            return

        if not brand:
            QMessageBox.critical(self, "Error", "Please enter the brand.")
            return

        if not remote_model:
            QMessageBox.critical(self, "Error", "Please enter the remote model.")
            return

        ir_data = self.parse_ir_file(file_path)
        if ir_data is None:
            return  # Parsing failed, already handled

        self.progress_bar.setValue(50)
        ir_content = self.create_ir_content(brand, remote_model, device_model, ir_data)

        self.progress_bar.setValue(75)
        self.save_ir_file(brand, remote_model, ir_content, os.path.basename(file_path))

        self.progress_bar.setValue(100)
        self.output_text.append("Processing completed successfully.")

        # Save user preferences
        self.save_preferences()

def main():
    app = QApplication(sys.argv)
    formatter = IRFileFormatter()
    formatter.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
