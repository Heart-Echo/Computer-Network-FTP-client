import socket
import os

def write_file():
    lines = []
    # build the complete ftp_core.py content
    lines.append('"""')
    lines.append('\u0066\u0074\u0070\u005f\u0063\u006f\u0072\u0065 - ftp protocol with FTPS')
    lines.append('"""')
    lines.append('')
    lines.append('import ssl')
    lines.append('import socket')
    lines.append('import os')
    lines.append('import re')
    lines.append('import time')
    lines.append('from typing import Optional, Tuple, List')
    lines.append('')
    
    with open('ftp_core.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('ok')
	
write_file()
