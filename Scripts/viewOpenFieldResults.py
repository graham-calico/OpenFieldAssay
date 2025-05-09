#!/home/graham/anaconda2/bin/python
import os, cv2, sys, numpy as np, argparse
import scipy.stats

def writeMovie(sourceVid,outputMovie,imgMaker):
  # open the input file
  cap = cv2.VideoCapture(sourceVid)
  if not( cap.isOpened()): raise ValueError("not opened")
  speedFps = cap.get(cv2.CAP_PROP_FPS)
  count = 0
  imgOk,img = cap.read()
  # create the output file
  if imgOk:
    imgH,imgW = img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
    outvid = cv2.VideoWriter(outputMovie,fourcc,
                             speedFps,(imgW,imgH))
    while imgOk:
      outImg = imgMaker.makeImg(img,count)
      outImg = np.uint8(outImg)
      outvid.write(outImg)
      imgOk,img = cap.read()
      # iterate and print count
      count += 1
      if count % int(speedFps) == 0: sys.stdout.write('.')
      if count % (speedFps * 50) == 0: sys.stdout.write('\n')
      sys.stdout.flush()
    outvid.release()
  cap.release()

# assumes coords are (x,y) for (head,tail)
# accepted states: none, hand, mouse
class TraceDrawer:
  def __init__(self,traceFile,stateFile,avgN,tailN,allowInconstV=False):
    self._avgN,self._tailN = avgN,tailN
    # do all the math in the constructor
    fT,fS = open(traceFile),open(stateFile) # remove headers
    srcVidT,srcVidS = fT.readline().rstrip(),fS.readline().rstrip()
    if srcVidT!=srcVidS:
      if not(allowInconstV):
        raise ValueError('inconsistent source videos')
    self._srcVid = srcVidT
    traceL,stateL = fT.readlines()[1:],fS.readlines()[1:]
    fT.close(),fS.close()
    self._stateL = list(map(lambda i: i.split()[0], stateL))
    self._handPrbL = list(map(lambda i: float(i.split()[1]), stateL))
    self._handEnd = 0 # default: nothing is shown
    self._posL,self._angL = [],[]
    for trTxt in traceL:
      getCrd = lambda i: list(map(float,i.split(',')))
      hdXy,tlXy = list(map(getCrd, trTxt.rstrip().split('\t')))
      posXy = list(map(lambda n: (hdXy[n]+tlXy[n])/2.0, [0,1]))
      ang = np.arctan2(hdXy[0]-tlXy[0],hdXy[1]-tlXy[1])
      self._posL.append(tuple(posXy))
      self._angL.append(ang)
    if avgN==1: self._okL = list(map(lambda i:True, self._posL))
    else:
      posHold,angHold = self._posL,self._angL
      self._posL,self._angL,self._okL = [],[],[]
      sideW = int(avgN/2)
      for n in range(len(posHold)):
        if n < sideW or n + sideW >= len(posHold):
          self._okL.append(False)
          self._posL.append('N/A')
          self._angL.append('N/A')
        else:
          self._okL.append(True)
          locAngL = angHold[n-sideW:n+sideW+1]
          locPosL = posHold[n-sideW:n+sideW+1]
          locX = np.mean(list(map(lambda i:i[0], locPosL)))
          locY = np.mean(list(map(lambda i:i[1], locPosL)))
          self._posL.append( (locX,locY) )
          self._angL.append( scipy.stats.circmean(locAngL) )
    # make these set-able
    self._lineColor = (250,210,20)
    self._dirColor = (20,210,20)
  def setLineColor(self,bgrTuple):
    self._lineColor = bgrTuple
  def setDirColor(self,bgrTuple):
    self._dirColor = bgrTuple
  def sourceVid(self): return self._srcVid
  def setHandEndHmm(self):
    # first non-hand frame after last hand block
    # in first half of video
    handL = list(filter(lambda n: self._stateL[n]=='hand', range(self._len)))
    handL = list(filter(lambda n: n < self._len/2, handL))
    if len(handL)==0: self._handEnd = 0
    else: self._handEnd = max(handL)+1
  def setHandEndBest(self):
    # this is a hack: start with the highest 'hand' value,
    # go until probability drops to 1/10 of that
    pFrL = [(self._handPrbL[n],n) for n in range(len(self._handPrbL))]
    handP,fN = max(pFrL)
    while fN < len(self._handPrbL) and self._handPrbL[fN]*10 > handP: fN += 1
    if fN==len(self._handPrbL):
      raise ValueError('ends with hand')
    self._handEnd = fN
  def makeImg(self,inImg,imgN): # zero-indexed
    brSz = 10
    # here, I only exclude if it is before the hand
    if imgN >= self._handEnd:
      outImg = np.copy(inImg)
      # draw the tail
      tA = max([0,imgN-self._tailN])
      for tN in range(tA,imgN):
        if self._okL[tN] and self._okL[tN+1]:
          if self._stateL[tN]=='mouse' and self._stateL[tN+1]=='mouse':
            pA = tuple(int(x) for x in self._posL[tN])
            pB = tuple(int(x) for x in self._posL[tN+1])
            cv2.line(outImg,pA,pB,color=self._lineColor,thickness=2)
      # draw the current status
      if self._okL[imgN]:
        color,rad = self._dirColor,3
        pLoc = tuple(int(x) for x in self._posL[imgN])
        cv2.circle(outImg,pLoc,rad,color=color,thickness=-1)
        aLen,aWid = 30,10
        aX = aLen * np.sin(self._angL[imgN]) + self._posL[imgN][0]
        aY = aLen * np.cos(self._angL[imgN]) + self._posL[imgN][1]
        pA = tuple(int(x) for x in [aX,aY])
        for rot in np.radians(90),np.radians(-90):
          bX = 0.5 * aWid * np.sin(self._angL[imgN]+rot) + self._posL[imgN][0]
          bY = 0.5 * aWid * np.cos(self._angL[imgN]+rot) + self._posL[imgN][1]
          pB = tuple(int(x) for x in [bX,bY])
          cv2.line(outImg,pA,pB,color=color,thickness=2)
    else: # state is NOT 'mouse', so just draw border
      outImg = np.zeros(inImg.shape)
      outImg[:,:] = np.array([20,230,250])
      h,w = inImg.shape[:2]
      outImg[brSz:h-brSz,brSz:w-brSz,:] = inImg[brSz:h-brSz,brSz:w-brSz,:]
    return outImg



def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("-t","--trace_file",
                  help="trace file")
  ap.add_argument("-s","--state_file",
                  help="state file")
  ap.add_argument("-o","--output_mov",
                  help="the ouput movie of mask (or box) images")
  ap.add_argument("--start_type",
                  help="how to define the beginning of analysis (hmm or best)")
  ap.add_argument("--avg",help="number of frames to average across. odd num; default==1",
                  default='1')
  ap.add_argument("--tail",help="number of frames to show the position trail; default==0",
                  default='0')
  ap.add_argument("--line_color",help="set bgr color (comma-separated ints, 0-255)",
                  default='3,200,255')
  ap.add_argument("--dir_color",help="set bgr color (comma-separated ints, 0-255)",
                  default='220,255,5')
  ap.add_argument("--allow_inconsistent",help="allow diff source videos",
                  action='store_true')
  args = vars(ap.parse_args())

  outMov = args["output_mov"]
  traceFile = args["trace_file"]
  stateFile = args["state_file"]
  avgWindow = int(args["avg"])
  if avgWindow < 1: raise ValueError("--avg must be positive")
  if avgWindow % 2 != 1: raise ValueError("--avg must be odd")
  tailSize = int(args["tail"])
  if tailSize < 0: raise ValueError("--tail can't be negative")
  
  drawer = TraceDrawer(traceFile,stateFile,avgWindow,tailSize,
                       allowInconstV=args['allow_inconsistent'])
  if args['start_type']:
    if args['start_type']=='hmm': drawer.setHandEndHmm()
    elif args['start_type']=='best': drawer.setHandEndBest()
    else: raise ValueError("--start_type must be hmm or best")
  if args['line_color']!='default':
    color = tuple(map(int,args['line_color'].split(',')))
    if len(color)!=3: raise ValueError('3-number color')
    drawer.setLineColor(color)
  if args['dir_color']!='default':
    color = tuple(map(int,args['dir_color'].split(',')))
    if len(color)!=3: raise ValueError('3-number color')
    drawer.setDirColor(color)

  inMov = drawer.sourceVid()
  writeMovie(inMov,outMov,drawer)
  print('done.')

if __name__ == "__main__": main()
