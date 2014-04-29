import os
import sys
import logging


class Pid:
    '''
    usage:
        pidinstance = Pid("./testpid")
        if(pidinstance.read()!=0):
            #errorhandling
        if(pidinstance.write()!=0):
            #errorhandling
            
        #program
        
        pidinstance.release()
    '''
    
    def __init__(self, lock_file):
        self.lock_file = os.path.expanduser(lock_file)
    
    def read(self):
        '''
        Pid.read:
            Tries to read lock_file
        Return values:
            0   :   lock_file does not exist, or no longer in use
            1   :   Lock_file in use
        '''
        try:
            pidfile = open(self.lock_file, "r")
            old_pid = pidfile.readline()
            pidfile.close()
            if (os.path.exists("/proc/%s" % old_pid)):
                logging.warning("Already running as pid:{0}".format(old_pid))
                return 1
            else:
                logging.warning("pid_file is there but process is not running, removing lock..")
                os.unlink(self.lock_file)
                return 0
        except IOError:
            pass
        logging.info("pid.read, lock file does not exist")
        return 0
            
    def write(self):
        '''
        Pid.write:
            Writes currend pid into lock_file
        Return values:
            0   :   ok
            1   :   error
        '''
        try:
            pidfile = open(self.lock_file, "w")
            pidfile.write(str(os.getpid()))
            pidfile.close()
            return 0
        except IOError:
            pass
        logging.error("Pid.write, could not write lock file")
        return 1
        
    def release(self):
        '''
        Pid.release:
            release current lock file
        '''
        try:
            os.unlink(self.lock_file)
            return 0
        except IOError:
            pass
        logging.error("Pid.release, could not release lock file")
        return 1    
      
'''    
tests  
pidinstance = Pid("./testpid")

print(pidinstance.read())
print(pidinstance.write())
input("press enter")
print(pidinstance.read())
print(pidinstance.release())
'''