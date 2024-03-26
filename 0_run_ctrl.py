#this code is for applying the workflow over all folders ending in "cam" in dir
import os, subprocess, argparse, time
import numpy as np

####-------------------FUNC/METH-----------------####
def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser( description='Screen JPG data by modify timestamp. Example: python 0_hourscreen.py -i 401cam')
    parser.add_argument('-i', '--indir', dest='indir', type=str, required=True,
                        help='The directory to iterate through for this workflow.')
    parser.add_argument('-p', '--pre', dest='prefix', type=str, required=False, default = 'MB',
                        help='The prefix of directories to use in workflow. For example, our directories started with MA or MB.')
    return parser.parse_args()

####-------------------PROGRAM-----------------####
def runflow(indir, pre):
    cwd = os.getcwd()
    dirs = [f for f in os.listdir(indir) if os.path.isdir(f) == True and f.startswith(pre)]
    
    for num, val in enumerate(dirs):
        cmd0 = 'python 0_hourscreen.py -i {0}'.format(val)
        cmd1 = 'python 1_blurscreen.py -i {0}'.format(val)
        cmd2 = 'python 2_getPAI.py -i {0}'.format(val)
        print('Working on hourscreen for {0}'.format(val))
        t0 = time.time()
        subprocess.call(cmd0)
        t1 = time.time()
        print('Time for hourscreen is {0} seconds'.format(np.round(t1-t0,3))) #~0.5s
        print('Working on blurscreen for {0}'.format(val))
        subprocess.call(cmd1)
        t2 = time.time()
        print('Time for blurscreen is {0} seconds '.format(np.round(t2-t1,3))) #~6.5s
        print('Working on PAI for {0}'.format(val))
        subprocess.call(cmd2)
        t3 = time.time()
        print('Time for PAI is {0} seconds'.format(np.round(t3-t2,3))) #~11.4s

if __name__ == '__main__':

    #####Parse command line
    inps = cmdLineParse()
    runflow(inps.indir, inps.prefix)
