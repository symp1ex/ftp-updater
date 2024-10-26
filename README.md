# ftp-updater
Utility for updating Windows applications from an ftp server.

The releases contain a compiled test version that accepts data for connecting to an FTP server (login and password) in clear text, without encryption. You can use it, but for security purposes I recommend reading the description below and rebuilding your version using encryption and unique keys.

It is assumed that the compiled executable file of the utility is located in the "updater" directory; the "updater" directory must be located in the root of the application being updated. 
The operating logic is as follows: the utility checks the version of the exe file specified in the config ("updater.json") ("exe_name"), which lies next to the "updater" directory. Then it checks the file version on the ftp server along the path that is also specified in the config (“ftp_path”). If the file version on the ftp server is higher, then the utility downloads the entire contents of the "ftp_path" directory, preserving its structure. 
When launched, the utility itself makes a copy of itself into a temporary folder and works from it; this is done so that the utility can update itself.

The "tools" directory contains auxiliary python scripts that are not needed for the utility to work, but are required for initial setup.

The script "get-hash.py" is a kind of fool proof. When updating from an ftp server, in addition to the version of the exe file, the utility generates a hash based on this exe file and compares it with what is specified in the metadata of the exe file in the "LegalCopyright" field. If the hashes do not match, the update will not occur. Those. When you've compiled a new version of your program, you need to put its executable file next to "get-hash.py" and run it. The result of the work will be a text file containing a hash, which must then be added to the metadata of the executable file of your program in the "LegalCopyright" field. Don't forget to replace the key with yours in the script itself "get-hash.py" (line 25) and in "updater.py" (line 84) before compiling "updater.py". The key can be any random set of characters of any length.

The scripts "crypto-key.py" and "gen-key.py" are used to encrypt the login and password for the fpt server so as not to store them in clear form in "updater.json".
Run the script "gen-key.py" to generate your unique key. Replace the value of "key" in "updater.py" (line 95) with this key before compiling "updater.py". In the "crypto-key.py" script, specify the key obtained at the previous stage (line 18), indicate your ftp server login (line 19) and password (line 20), and then run "crypto-key.py". As a result, you will receive a text document with the login and password from the ftp server in encrypted form, which must be used in “updater.json”.

The path for sending files to ftp-server is written directly in the code: "..\\date", i.e. the entire contents of the "date" folder is sent, which should be located in the root of the main application.
