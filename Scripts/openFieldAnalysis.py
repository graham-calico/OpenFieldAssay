# special because I need to run analysis for v1 and v2, separately.
# also, since these are white boxes, I want to try using my HMM parse
# of "hand" and compare it to my use-highest-score
import os, cv2, sys, numpy as np, argparse
import scipy.stats, math

def getStatsFromDir(cornerFL,dTrace=False,dState=False):
  if not(dTrace): raise ValueError("needs a trace directory")
  if not(dState): raise ValueError("needs a state directory")
  if len(cornerFL)==0: raise ValueError("needs corner file(s)")
  # provided as 430mm (0.43m) in email from Johannes Riegler on Oct19,2020
  boxDim = 0.43
  # all potential data files
  fL_t = list(map(lambda i: os.path.join(dTrace,i), os.listdir(dTrace)))
  fL_t = list(filter(lambda i: i.split('.')[-1]=='txt', fL_t))
  fL_s = list(map(lambda i: os.path.join(dState,i), os.listdir(dState)))
  fL_s = list(filter(lambda i: i.split('.')[-1]=='txt', fL_s))
  # match up the state & trace files (names should be the same)
  if len(fL_t)!=len(fL_s):
    # don't raise exception yet, just print: file-by-file
    # error message will be more useful
    sys.stderr.write("Uneven file counts:\n")
    sys.stderr.write("State:\t"+str(len(fL_s))+"\n")
    sys.stderr.write("Trace:\t"+str(len(fL_t))+"\n")
    sys.stderr.flush()
  baseToF_t,baseToF_s = {},{}
  for f in fL_t: baseToF_t[os.path.basename(f)] = f
  for f in fL_s: baseToF_s[os.path.basename(f)] = f
  # now check 1:1 correspondence
  for fb in baseToF_t.keys():
    if not(fb in baseToF_s):
      raise ValueError(fb+' missing in state dir')
  for fb in baseToF_s.keys():
    if not(fb in baseToF_t):
      raise ValueError(fb+' missing in trace dir')
  # get the corner stats first
  srcToCornerL = {}
  for cornerF in cornerFL:
    f = open(cornerF)
    for i in f.readlines():
      srcF,cStr = i.rstrip().split('\t')
      srcToCornerL[srcF] = eval(cStr)
    f.close()
  # now get the file-by-file, frame-by-frame data
  statsL = []
  for fb in baseToF_s.keys():
    traceF = baseToF_t[fb]
    stateF = baseToF_s[fb]
    statsL.append( OpenFieldStats(traceF,stateF,srcToCornerL,boxDim) )
  return statsL

class Line:
  def __init__(self,xy1,xy2):
    if xy1==xy2: raise ValueError('points cant be equal for line')
    self._xy1 = xy1
    self._xy2 = xy2
  def dist(self,xy):
    x0,y0 = xy
    x1,y1 = self._xy1
    x2,y2 = self._xy2
    # eq for dist from line defined by 2 points
    numer = abs( (x2-x1)*(y1-y0) - (x1-x0)*(y2-y1) )
    denom = math.sqrt( (x2-x1)**2 + (y2-y1)**2 )
    return float(numer)/denom

def getEdgeLines(cornerL):
  cornerL = list(map(lambda i:i, cornerL))
  cornerL.sort() # on x coord
  leftL,rightL = cornerL[:2],cornerL[2:]
  # sort each on y coord
  for sL in [leftL,rightL]:
    if sL[0][1] > sL[1][1]: sL.reverse()
  leftS = Line(leftL[0],leftL[1])
  rightS = Line(rightL[0],rightL[1])
  topS = Line(leftL[0],rightL[0])
  bottomS = Line(leftL[1],rightL[1])
  return [leftS,rightS,topS,bottomS]

# I'm going to assume that the video image
# is just a plane, and I'm just converting
# a pixel to its actual length.  Also assumes
# the box is square (both dims the same)
def getPixelSize(cornerL,boxDim):
  cornerL = list(map(lambda i:i, cornerL))
  cornerL.sort() # on x coord
  leftL,rightL = cornerL[:2],cornerL[2:]
  # sort each on y coord
  for sL in [leftL,rightL]:
    if sL[0][1] > sL[1][1]: sL.reverse()
  def getDist(xyA,xyB):
    xD,yD = xyA[0] - xyB[0],xyA[1] - xyB[1]
    return math.sqrt(xD**2 + yD**2)
  lD = getDist(leftL[0],leftL[1])
  rD = getDist(rightL[0],rightL[1])
  tD = getDist(leftL[0],rightL[0])
  bD = getDist(leftL[1],rightL[1])
  return boxDim / np.mean([lD,rD,tD,bD])


# assumes coords are (x,y) for (head,tail)
# REQUIRES that srcToCornerL has a source-file key and
# contains 4 (x,y) coordinates (in any order)
class OpenFieldStats:
  def __init__(self,traceFile,stateFile,srcToCornerL,boxDim):
    self._args = (traceFile,stateFile,srcToCornerL,boxDim)
    self._ready = False
    self._useVideoBase = False
  def useVideoBase(self):
    self._useVideoBase = True    
  def getReady(self):
    if not(self._ready): self._readyHelp()
  def _readyHelp(self):
    self._ready = True
    traceFile,stateFile,srcToCornerL,boxDim = self._args
    fT,fS = open(traceFile),open(stateFile) # remove headers
    srcVidT,srcVidS = fT.readline().rstrip(),fS.readline().rstrip()
    if self._useVideoBase:
      srcFullVidL = [srcVidT,srcVidS]
      srcVidS = os.path.basename(srcVidS)
      srcVidT = os.path.basename(srcVidT)
      oldStcD = srcToCornerL
      srcToCornerL = {}
      for oldS in oldStcD.keys():
        newS = os.path.basename(oldS)
        if newS==srcVidT: srcFullVidL.append(oldS)
        if newS in srcToCornerL:
          raise ValueError("vid basename used twice: "+newS)
        srcToCornerL[newS] = oldStcD[oldS]
    if srcVidT!=srcVidS:
      print('')
      print("srcVidT:\t"+srcVidT)
      print("srcVidS:\t"+srcVidS)
      raise ValueError('inconsistent source videos')
    if not(self._useVideoBase): srcFullVidL = [srcVidT]
    fpsL = []
    for sv in srcFullVidL:
      cap = cv2.VideoCapture(sv)
      fps = cap.get(cv2.CAP_PROP_FPS)
      cap.release()
      if len(fpsL) > 0 and fps!=fpsL[0]:
        raise ValueError('inconsistent fps for eq. vid files')
      else: fpsL.append(fps)
    self._fps = fpsL[0]
    self._srcVid = srcVidT
    # SCALING DATA
    self._cornerXyL = list(map(lambda i:i, srcToCornerL[srcVidT]))
    self._edgeLines = getEdgeLines(self._cornerXyL)
    self._pixSize = getPixelSize(self._cornerXyL,boxDim)
    # CONTINUE PARSING
    headerT,headerS = fT.readline().rstrip(),fS.readline().rstrip()
    if headerT!='head\ttail':
      raise ValueError('bad header for trace: '+headerT)
    if headerS!='parse\thand\tnone\tmouse':
      raise ValueError('bad header for state: '+headerT)
    traceL,stateL = fT.readlines(),fS.readlines()
    fT.close(),fS.close()
    if len(traceL)!=len(stateL):
      self._success = False
      print('\n'+traceFile+':\t'+str(len(traceL)))
      print(stateFile+':\t'+str(len(stateL)))
#      raise ValueError('non-matching trace/state lengths')
    else: # should be all cases, but if not, I can survey
      self._success = True
      self._stateL = list(map(lambda i: i.split()[0], stateL))
      self._handPrbL = list(map(lambda i: float(i.split()[1]), stateL))
      self._posL,self._angL = [],[]
      for trTxt in traceL:
        getCrd = lambda i: list(map(float,i.split(',')))
        hdXy,tlXy = list(map(getCrd, trTxt.rstrip().split('\t')))
        posXy = list(map(lambda n: (hdXy[n]+tlXy[n])/2.0, [0,1]))
        ang = np.arctan2(hdXy[0]-tlXy[0],hdXy[1]-tlXy[1])
        self._posL.append(tuple(posXy))
        self._angL.append(ang)
      self._len = len(self._posL)
      # CONSTANT: I will average across 15 frames (1/2 second)
      avgN = 15
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
  def sourceVid(self):
    if self._ready: return self._srcVid
    else:
      traceFile,stateFile,srcToCornerL,boxDim = self._args
      f = open(traceFile)
      srcName = f.readline().strip()
      f.close()
      return srcName
  def success(self): return self._success
  def fps(self): return self._fps
  def len(self): return self._len
  def getHandEndHmm(self):
    # first non-hand frame after last hand block
    # in first half of video
    handL = list(filter(lambda n: self._stateL[n]=='hand', range(self._len)))
    handL = list(filter(lambda n: n < self._len/2, handL))
    if len(handL)==0: return -1
    else:
      firstNon = max(handL)+1
      if self._stateL[firstNon]=='hand': return -1
      else: return firstNon
  def getHandEndBest(self):
    # this is a hack: start with the highest 'hand' value,
    # go until probability drops to 1/10 of that
    pFrL = [(self._handPrbL[n],n) for n in range(int(self._len/2))]
    handP,fN = max(pFrL)
    while fN < len(self._handPrbL) and self._handPrbL[fN]*10 > handP: fN += 1
    if fN==len(self._handPrbL):
      pass
      # print("ends with hand problem")
      # raise ValueError('ends with hand')
    return fN
  def getHandLast(self):
    # this is a hack to allow manual correction:
    # start analysis after the last frame labelled 'hand'
    # in first half of video
    handL = list(filter(lambda n: self._stateL[n]=='hand', range(self._len)))
    if len(handL)==0: return -1
    else:
      firstAfterHand = max(handL) + 1
      if firstAfterHand >= len(self._stateL): return -1
      else: return firstAfterHand
  # both of these NORMALIZE to account for
  # missing (non-mouse) frames
  def getLinearDist(self,startN,endN,step):
    dSum,fSum = 0.0,0
    for nA in range(startN,endN+1,step):
      nB = nA + step
      if nB < self._len and self._okL[nA] and self._okL[nB]:
        if self._stateL[nA]=='mouse' and self._stateL[nB]=='mouse':
          pA,pB = self._posL[nA],self._posL[nB]
          d = math.sqrt( (pA[0]-pB[0])**2 + (pA[1]-pB[1])**2 )
          dSum += d
          fSum += 1
    if fSum==0: raise ValueError('no valid frame intervals')
    # returns in units of meters (analysis was in pixels)
    return dSum * self._pixSize
  def getAngularDist(self,startN,endN,step):
    aSum,fSum = 0.0,0
    for nA in range(startN,endN+1,step):
      nB = nA + step
      if nB < self._len and self._okL[nA] and self._okL[nB]:
        if self._stateL[nA]=='mouse' and self._stateL[nB]=='mouse':
          a = self._angL[nA] - self._angL[nB]
          a = (a + math.pi) % (2 * math.pi) - math.pi
          a = abs(a)
          aSum += a
          fSum += 1
    if fSum==0: raise ValueError('no valid frame intervals')
    return aSum
  def getTimeAwayFromWall(self,startN,endN,wallDist):
    frNL,distL = self.getEdgeDistArray(startN,endN,1)
    farL = list(filter(lambda d: d >= wallDist, distL))
    return float(len(farL))/len(distL)
  # returns x,y lists of values for time,dist-from-nearest-side
  def getEdgeDistArray(self,startN,endN,step):
    frNL,distL = [],[]
    for nA in range(startN,endN+1,step):
      if nA < self._len and self._okL[nA] and self._stateL[nA]=='mouse':
          xyA = self._posL[nA]
          dL = list(map(lambda s: s.dist(xyA), self._edgeLines))
          frNL.append(nA - startN)
          distL.append(min(dL) * self._pixSize)
    return frNL,distL
  # step is in frames, stretch is # steps
  def getGaitSpeed(self,startN,endN,step,stretch,fps):
    distL = [] # step distances
    bigDistL = [] # stretch distances
    for nA in range(startN,endN+1,step):
      nB = nA + step
      if nB < self._len and self._okL[nA] and self._okL[nB]:
        if self._stateL[nA]=='mouse' and self._stateL[nB]=='mouse':
          pA,pB = self._posL[nA],self._posL[nB]
          d = math.sqrt( (pA[0]-pB[0])**2 + (pA[1]-pB[1])**2 )
          distL.append( d )
          if len(distL) % stretch == 0:
            bigDistL.append(sum(distL[-stretch:]))
    if len(distL)==0: raise ValueError('no valid frame intervals')
    if len(bigDistL)==0: raise ValueError('no valid BIG frame intervals')
    # eliminate zero-distance intervals, they'd have no weight
    bigDistL = list(filter(lambda d: d > 0, bigDistL))
    if len(bigDistL)==0: return 0.0
    else:
      # weighted average of dist/frame, weighted by dist
      bigDistA = np.array(bigDistL)
      avgSpeed = np.average(bigDistA,weights=bigDistA)
      # normalize to deliver meters/sec
      return avgSpeed * self._pixSize * step * stretch / fps
    
    

def roundFps(fps):
  iFps = int(fps)
  if fps - iFps >= 0.5: iFps += 1
  return iFps


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("-t","--trace_dir",
                  help="directory with .txt files for trace results")
  ap.add_argument("-s","--state_dir",
                  help="directory with .txt files for state results")
  ap.add_argument("-c","--corner_file",
                  help="a file of corner coordinates (can be used multiple times)",
                  action='append')
  ap.add_argument("-b","--begin_type",
                  help="how to define the beginning of analysis (hmm or best or last)",
                  default='hmm')
  ap.add_argument("--adjust_fps",
                  help="do NOT assume 30fps, instead observe & adjust to true fps",
                  action='store_true')
  ap.add_argument("--use_video_base",
                  help="allow the paths in the state/trace/corner files to differ",
                  action='store_true')
  ap.add_argument("--time_min",
                  help="how long to analyze behavior, in minutes (default: 10)",
                  default='10')
  ap.add_argument("--header",
                  help="include a header line in the output",
                  action='store_true')
  args = vars(ap.parse_args())

  usingVidBase = args["use_video_base"]
  
  if args['begin_type']!='hmm' and args['begin_type']!='best' and args['begin_type']!='last':
    raise ValueError("--start_type must be hmm or best or last")
  # otherwise, assume (test for) 30fps
  doAdjFps = args['adjust_fps']

  anLenInMin = float(args['time_min'])
  analysisLen = anLenInMin * 60 # in seconds
  # OLD DEFAULT: analysisLen = 600 # 10 minutes, in seconds
  skipAfterHand = 1 # second
  offWallDistance = 0.074 # in meters

  getName = lambda v: os.path.basename(v.sourceVid())
  vidDataL = getStatsFromDir(args['corner_file'],
                             dTrace=args['trace_dir'],
                             dState=args['state_dir'])
  nameVidL = [(getName(v),v) for v in vidDataL]
  nameVidL.sort()
  
  headL = ['Video', 'dist(meters)', 'rot(radians)',
           'distPerRot(m/rad)','f(middle)','gspeed(m/sec)',
           'start(frame)','start(sec)']
  if args["header"]: sys.stdout.write('\t'.join(headL) + '\n')
  
  for name,vid in nameVidL:
    sys.stdout.write(name+'\t')
    sys.stdout.flush()
    if usingVidBase: vid.useVideoBase()
    vid.getReady()
    # check & adjust to fps
    if doAdjFps: locFps = vid.fps()
    else:
      locFps = 30
      if roundFps(vid.fps())!=locFps:
        print('Actual fps: '+str(vid.fps()))
        raise ValueError(name+' was not at 30fps')
    if not(vid.success()):
      start = 0
    elif args['begin_type']=='hmm':
      start = vid.getHandEndHmm()
    elif args['begin_type']=='best':
      start = vid.getHandEndBest()
    elif args['begin_type']=='last':
      start = vid.getHandLast()
    else: raise ValueError('start_type problem')
    if start==-1: raise ValueError('bad hand')
    start += int(skipAfterHand * locFps)
    end = start + int(analysisLen * locFps)
    prL = []
    if not(vid.success()) or end > vid.len():
      for n in range(5): prL.append('N/A')
    else:
      prL.append( vid.getLinearDist(start,end,roundFps(locFps/2)) )
      prL.append( vid.getAngularDist(start,end,roundFps(locFps/2)) )
      prL.append( prL[-2] / prL[-1] )
      prL.append( vid.getTimeAwayFromWall(start,end,offWallDistance) )
      # 1-second intervals, 1/2-second position measurements
      prL.append( vid.getGaitSpeed(start,end,roundFps(locFps/2),1,locFps) )
    prL.append( start )
    prL.append( start / locFps )
    print('\t'.join(list(map(str,prL))))

if __name__ == "__main__": main()
