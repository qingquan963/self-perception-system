Set WshShell = WScript.CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d C:\Users\Administrator\.openclaw\production\data\vector_store && pythonw api_server.py", 0, False
