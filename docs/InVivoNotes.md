<p>
    <a href="https://docs.calicolabs.com/python-template"><img alt="docs: Calico Docs" src="https://img.shields.io/badge/docs-Calico%20Docs-28A049.svg"></a>
    <a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

[Back to home.](../README.md)

# <i>In Vivo</i> Protocol
This section provides guidance for the collection of data in the vivarium, in a manner that will maximize compatability
with this software system.  Researchers should obtain approval from their IACUC before performing any of these procedures.

## Pre-Run Preparation
We recommend bringing the cages into the procedure room at least an hour before starting the experiment 
so that the animals are accustomed to the room and are as calm as possible.  
Boxes should be cleaned as described below ahead of the first run, and also after the final run of the day/session.

## Performing & Recording a Run
Camera view/placement should be checked and adjusted if necessary before each run begins.  The camera should
not be adjusted once recording has begun.

Video recording should start ahead of placing the mouse in the box (ideally, within a minute or two).
Mice should be handled non-aversively (by tunneling or cupping) to move them into the boxes.
Our software automatically detects placement of the mice in the box and defines that time point as time "zero".
These ML models are trained with images of lab personnell wearing full-sleeve lab coats (generally white or blue)
and gloves (generally blue or purple), and handling the mice with tunneling or cupping (we used red translucent plastic
tunnels).  Models are trained through augmentation to be robust to alternative lab coat & glove colors.

<b>Researchers should only reach into the box once during each recording run: when they are placing the mouse in the box.</b>
After all mice being recorded at a time have been placed, we recommend that researchers quietly exit the procedure room.
If they stay in the room, they should remain quiet, still, and out-of-sight from the mice.
Our system defaults to a 10 minute analysis, starting when the placement of the mouse in the box has been detected.
Researchers should wait slightly longer than the desired analysis time before re-entering the room.
<b>Video recording should be stopped before removing mice from the boxes.</b> 

When videos are saved, the file names should contain enough information to identify the mouse and recording instance.
This analysis system will report statistics for each video file and does not keep track of accompanying meta-data.  Your
video file names must be unique, at least across the study where they will be analyzed in parallel.

<i>Optional:</i> researchers may place a post-it note on the upper left side of the box with identifying information
for the run (e.g. mouse ID).  This can allow downstream auditing of data labels.  
This system is generally robust against this added item, but is not trained against all possible note sizes/shapes/colors.
If you include a post-it, we recommend similar placement and appearance as in the sample image below.

<img src="imgs/emptyBoxWithLabel.png" width=80%>

Post-it notes should be added before the video recording is started and removed after it is finished, and ahead of box cleaning.

## Cleaning Between Runs
Boxes are cleaned in between runs.  We first use a wet paper towel to remove excrement, then use 
[this](https://www.coneinstruments.com/product/Protex-One-Step-Disinfectant-Spray-CI?option=911449)
quaternary ammonia based disinfectant, spraying all inner surfaces thoroughly.  We let the disinfectant
sit for one minute, then wipe all surfaces dry with clean paper towels.  


