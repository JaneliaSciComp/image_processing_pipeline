from app import app
from app.settings import Settings

app.run(debug=True, host=Settings.serverInfo["IP"], port=Settings.serverInfo["port"])
