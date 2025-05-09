import os, tkinter as tk, cv2, sys
import PIL.Image, PIL.ImageTk
import argparse

def collectNthFrame(vidFile,frameN=0):
  cap = cv2.VideoCapture(vidFile)
  ret,img = cap.read()
  if not(ret):
    raise ValueError("no frames in "+vidFile)
  initFrN = frameN
  while ret and frameN > 0:
    ret,img = cap.read()
    frameN -= 1
  if frameN > 0:
    raise ValueError("video ends before frame "+str(initFrN))
  cap.release()
  return img

def collectFps(vidFile):
  cap = cv2.VideoCapture(vidFile)
  fps = cap.get(cv2.CAP_PROP_FPS)
  cap.release()
  return fps

class KeyPoint:
  def __init__(self,x,y):
    self._x,self._y = x,y
  def x(self): return self._x
  def y(self): return self._y


class ImgView(tk.Frame):
  def __init__(self, imgManager, master=None):
    tk.Frame.__init__(self, master)
    self._armLen = 10
    self._imgMang = imgManager
    #self._numKp = len(kpNameL)
    #self._kpNameL = map(lambda i:i, kpNameL)
    self._catL = [] #map(lambda i: 'Add '+i, kpNameL)
    self._catL.extend(['Erase','Skip 5sec','Record','Quit'])
    self._nCat = len(self._catL)
    self._newColor = "cyan"
    self._markW,self._markH = 50,10
    # dimensions for image panel
    self._imgH,self._imgW = 0,0
    self._kpL = []
    imgManager.initiateSort()
    if imgManager.isSorting():
      imgF = imgManager.getImgFile()
      print(imgF)
      self._img = collectNthFrame(imgManager.getImgFile())
      self._imgH,self._imgW = self._img.shape[:2]
    # start the display
    self.grid()
    self._createWidgets()
    if imgManager.isSorting():
      self.display()
      self._fiveSteps = 0

  def tapButton(self,label):
    if label=='Quit':
      self._imgMang.quit()
      self.quit()
    elif label=='Skip 5sec':
      self._fiveSteps += 1
      imgF = self._imgMang.getImgFile()
      fpSec = collectFps(imgF)
      frN = int(self._fiveSteps * fpSec * 5)
      self._img = collectNthFrame(imgF,frN)
      self.display()
      self._kpL = []
    elif label=='Record':
      self._imgMang.recordKPs(self._kpL)
      self._kpL = []
      self.displayNew()
    elif label.find('Add ')==0:
      if self._kp != None:
        labName = label[4:]
        color = self._colorL[self._colorN % len(self._colorL)]
        self._colorN += 1
        kp = self._kp
        self._kpL.append( (kp,labName,color) )
        self.eraseTempKP()
        self.drawKP(kp,color)
        self.markKpColor(labName,color)
    elif label=='Erase':
      if len(self._kpL) > 0:
        self._kpL = self._kpL[:-1]
        self.display()
        self.drawKpL(self._newColor)
    else:
      raise ValueError("unknown button label")

  def displayNew(self,replaceKPs=True):
    self._fiveSteps = 0
    # start by blanking the area
    self.imgDisp.create_rectangle(0,0,self._imgW,self._imgH,
                                  fill=self.cget('bg'))
    if not(self._imgMang.isSorting()):
      raise ValueError("can't display when image manager isn't iterating")
    imgF = self._imgMang.getImgFile()
    print(imgF)
    self._img = collectNthFrame(imgF)
    self.display()
  def display(self):
    self._frImg = cv2.cvtColor(self._img, cv2.COLOR_BGR2RGB)
    self._photo = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(self._frImg))
    self.imgDisp.create_image(0, 0, anchor=tk.NW, image=self._photo)
    self._imgRectExists = False

  # FUNCTIONS FOR DRAWING
  def drawKpL(self,color):
    for kp in self._kpL:
      w = self._armLen
      a = self.imgDisp.create_line(kp.x()-w,kp.y(),kp.x()+w,kp.y(),fill=color,width=2)
      b = self.imgDisp.create_line(kp.x(),kp.y()-w,kp.x(),kp.y()+w,fill=color,width=2)
  def markKpColor(self,name,color):
    self.markD[name].create_rectangle(0,0,self._markW,self._markH,fill=color)
  def makeKP(self, event):
    #Translate mouse screen x0,y0 coordinates to canvas coordinates
    x,y = self.imgDisp.canvasx(event.x), self.imgDisp.canvasy(event.y)
    # rotate through replacing KPs if they already exist
    if len(self._kpL)==4: self._kpL = self._kpL[1:]
    self._kpL.append( KeyPoint(x,y) )
    self.display()
    self.drawKpL(self._newColor)
    
  # PRIVATE USE
  def _createWidgets(self):
    self.buttonL = []
    for n in range(self._nCat):
      cat = self._catL[n]
      b = tk.Button(self, text=cat, command=self._makeImgUpdateButton(cat))
      b.grid(row=1,column=n)
      self.buttonL.append(b)
    if self._imgMang.isSorting():
      self.imgDisp = tk.Canvas(self, width=self._imgW, height=self._imgH)
      self.imgDisp.grid(row=2,column=0,columnspan=self._nCat)
      self.imgDisp.bind( "<Button-1>", self.makeKP )
  def _makeImgUpdateButton(self,label):
    def buttonTap():
      self.tapButton(label)
    return buttonTap

class VideoBoxSorter:
  def __init__(self,sourceFileName,recFileName):
    self._sourceFile = sourceFileName
    self._recFile = recFileName
    self._importKps()
  def _importKps(self):
    f = open(self._sourceFile)
    imgFileL = map(lambda i: i.strip(), f.readlines())
    f.close()
    imgFileL = map(lambda i: os.path.abspath(i), imgFileL)
    self._imfToKpL = {}
    for imgF in imgFileL:
      self._imfToKpL[imgF] = []
    if os.path.isfile(self._recFile):
      f = open(self._recFile)
      line = f.readline()
      while line:
        imgF,kpStr = line.strip().split('\t')
        if not(imgF in self._imfToKpL):
          raise ValueError("Listed image file doesn't exist:\n"+imgF)
        else:
          self._imfToKpL[imgF] = eval(kpStr)
        line = f.readline()
      f.close()
    self._isSrt = False
  def initiateSort(self):
    self._isSrt = True
    fullL = self._imfToKpL.keys()
    if len(fullL)==0: raise ValueError("no image files found")
    doneL = list(filter(lambda i: len(self._imfToKpL[i]) > 0, fullL))
    notDoneL = list(filter(lambda i: len(self._imfToKpL[i])==0, fullL))
    self._candL = notDoneL
    self._candL.extend(doneL)
    self._candN = 0
    if self._candN==len(self._candL): self._isSrt = False
  def numImages(self): return len(self._candL)
  def _next(self):
    self._candN += 1
    if self._candN==len(self._candL): self._isSrt = False
  def isSorting(self): return self._isSrt
  def getImgFile(self):
    return self._candL[self._candN]
  def recordKPs(self,kpL):
    kpL = map(lambda i: (i.x(),i.y()), kpL)
    imgF = self._candL[self._candN]
    self._imfToKpL[imgF] = list(map(lambda i:i, kpL))
    outf = open(self._recFile,'w')
    for imgF in self._candL:
      if len(self._imfToKpL[imgF]) > 0:
        outstr = imgF+'\t'+str(self._imfToKpL[imgF])+'\n'
        outf.write(outstr)
    outf.close()
    self._next()
  def quit(self): pass


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("-i","--input_fof",
                  help="the file-of-movie-files to be annotated")
  ap.add_argument("-o","--output_file",
                  help="will re-list the files along with box coords from each",
                  default=None)
  args = vars(ap.parse_args())
  
  sorter = VideoBoxSorter(args["input_fof"],args["output_file"])
  app = ImgView(sorter)
  app.master.title('Box Corners')
  app.mainloop()

if __name__ == "__main__": main()
