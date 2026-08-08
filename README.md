# READ ME - PM_liver_workflow
This is the gitlab repo for the University of Utrecht Business Informatics Master thesis of Linde van Werven.
Included in this repo is the code of the designed S2CF+C approach for preprocessing and comparing Symplicit90y software execution event data to compare the FLA workflow. 

## Included
In this repo the following things are included:
* code: holding the python files to execute the S2CF+C approach and it's two modules. An overview of the working of the approach and the included modules can be found in the thesis report chapter 7. More detailed information about the code can be found in the folder and as inline comments in the python files. 
* MBI-thesis-report-LvW.pdf: my thesis report including the key insights from developing and applying the S2CF+C approach. 

## Installation
For this project I used python version 3.14.0. This should just be downloaded on the [python website](https://www.python.org/downloads/).
These could be some helpfull powershell commands, notice that this could all look different on other machines. Examples are: if your python path is set up differently, different OS or different terminal.
After cloning this repository in a folder in your file explorer:
```
git clone https://github.com/LvanWerven/S2CFC-approach.git
```
A virtual python environment should be created (if you have the permisson to do that):
```
python -3.14 -m venv venv
# Then activate the virtual environment, do this everytime you are opening the project
venv/scripts/activate 
```
The other dependencies are listed in the requirements.txt and can be installed using the following command:
```
pip install -r requirements.txt
```

How to run the approach is in the readme.md in the code folder

## Authors and acknowledgment
Main author: Linde van Werven \
UMC Utrecht supervisor: Floris Reinders \
University of Utrecht supervisor: Xixi Lu \
UMC Utrecht second supervisor: Clemens Bos

