import os
def colorprint(txt,opt="222",end='\n'): 
    #print(f'\033[{opt}m',txt,'\033[0m',end=end)
    print(u"\u001b[38;5;"+opt+'m'+txt+u"\u001b[0m",end=end)