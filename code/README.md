# README - S2CF+C APPROACH
This README will describe how the S2CF+C_approach should be run and what is included in this folder. For more detailed information about the working, either read the thesis report or the respective code files. 

> *Disclaimers*
> * All the code written is not optimized or execution time / memory, executing it takes some time and is inefficiënt. I have implemented some print statements to show you that it is still running. That being said, if you haven't seen a new print statement for quite some time, wait longer. It is eager to show you errors, not keeping you informed on where it is in execution. However, if execution of the whole approach takes longer than 15min something did went wrong.
> * Some of the code has been generated with help of the LLM models Gemini of Google, Copilot of Microsoft
> * Gemini was used to improve functions, help with syntax or based on logic provided to generate a function.
> * Copilot of Microsoft was used for bugfixing and small code generation tasks, tasks that include error messages could include directory structure, log files with study IDs or other UMC Utrecht specific information were send to Copilot since this information (to my understanding) stays within the UMC Utrecht.
> All the code is understood, has been checked and were necessary improved by me

## run_S2CFC_approach.sh
This bash scripts runs the complete approach, twice the S2CF module (each for one dataset) and once the comparison module. Currently, this bash script is setup to run Pre- and Trial-AI-addition data, as stored in the respective folder paths. 

### How to run
The bash script can be run by opening a (git) bash terminal and executing the following command (if located in the code folder, otherwise replace **run_S2CFC_approach.sh** with the complete path to that file):
```
sh run_S2CFC_approach.sh [execution run name] [whether to include the Manual registration activity in the comparison]
```
The two parameters (in these brackets[]) should be changed to hold:
* execution run name = just a name that you want to give this time execution of the S2CF+C approach, will be used to name folders and files.
* exclude manual registration activity = as can be read in the thesis report this activity was excluded from the FLA comparison. The second parameter will indicate whether the activity will be include (True) or exclude (False). The default is excluding the activity.

### Changing the execution
Within this bash script the modules within the S2CF+C approach are called for execution. The parameters for these module calls are currently set for how it was run before 17/07/2026, a lot of tweaking is possible. 
More details about the parameters of the modules can be found within the respective python files. Or when trying to call the module from the bash terminal, and adding the help flag (-h):
```
"C:/Program Files/Python314/python.exe" -m pre_processing.S2CF_module -h
```
or 
```
"C:/Program Files/Python314/python.exe" -m comparison_analysis.comparison_module -h
```
If run without the help flag a list of required parameters is shown. 

Note that the **"C:/Program Files/Python314/python.exe"** part is how I needed to call python in the bash terminal, this could be another path or another way.

## Pre_processing
The pre-processing folder contains the code for developing and executing this phase of the approach. 
Included are:
* analysis helpers: python scripts that I used to explore the log files and confirm or debunk expectations. An example of how to run these is shown below.
* utils: this folder contains the helper functions used in the different steps of the S2CF module. These are only interesting if you want to deep dive in the inner workings of the module
* S2CF_config.py: contains the most important parameters for the inner working of the S2CF module such as the patterns presented in the execution event data, used to identify activities or pieces of information. This should first be updated if something goes wrong or if you want to make small changes. Check the  
* S2CF_module.py: contains the function calls for the execution of the S2CF module. 

### Example run analysis helper
```
"C:/Program Files/Python314/python.exe" -m analysis_helpers/identify_streaks --lfp "ADD COMPLETE PATH TO FOLDER WITH (AT LEAST ONE) EVENT LOG" --se "scheduling task: performing liver segmentation" --attribute "Message" --max_length="15"
```
This will go through the files in the folder, and start making lists with length 15 of the *Message* values starting from the *"scheduling task: performing liver segmentation"*. Then it will compare these list and any list that has only been found once will be filtered out. The found and filtered streaks will be outputted in the *"streaks_comparison"* folder in the input folder. 

### S2CF module
The execution of the S2CF module is split up in the three steps, data preperation, event abstraction and data refining. These three steps can be seperately executed by adding the *--execute* param and the names of the steps that should be executed. 

The **data preperation** step will create the *event data* folder in the working folder (given as the *--wfp* param). The .csv files in this folder will contain the the three SOFTWARE_DATA_COLUMS (see S2CF_config), the Log ID and Username. 

The **event abstraction** step will create the *event logs* folder. After the step has been concluded the .csv files in this folder will have the Activity and Activity marker column and each event found with one of the event abstraction functions will be marked with the corresponding activity.

The **data refining** step creates three folders:
* *grouped_per_case*: holds event logs, where each file contains the event logs for a single case.
* *filtered_per_case*: holds the filtered event logs (each file per case), where all events that are not part of a phase have been filtered out.
* *filtered_annotated_event_logs_per_case*: holds the filtered and annotated event logs (each file per case), where each event is one activity with a start and end time.


## Comparison_analysis
The comparison_analysis folder contains the code for developing and executing this phase of the approach. Included are:
* analysis helpers: holds a jupyter notebook to check outliers of activity execution durations or time between activity executions.
* jupyter notebooks: these notebooks were used to explore the data and the results of the comparison module, and create the comparison scripts in the first place. They are not necessary for running the approach, but can be used to explore the results.
* utils: this folder contains the helper functions used in the different steps of the comparison module. These are only interesting if you want to deep dive in the inner workings of the module.
* comparison_config.py: contains the most important parameters for the inner working of the comparison module such as the used configurations in the Process Comparator and the time units for the performance metrics of the trace durations.
* comparison_module.py: contains the function calls for the execution of the comparison module.

### Comparison module
The execution of the comparison module is split up in the three compmarisons, performance, behaviour and handovers. These three comparisons can be seperately executed by adding the *--execute* param and the names of the comparisons that should be executed. 

The **Performance comparison** step will create the *performance_comparison* folder in the output folder (given as the *--ofp* param). It will contain all the boxplots, tables and the sankey diagrams for the performance comparison.

The **Behaviour comparison** step will create the *behaviour comparison* folder. With the folders for each of the configurations of the Process Comparator. And the latex and .csv tables for the variant analysis of each of the datasets.

The **Handover comparison** step creates the *handover_comparison* folder. With a file containing the latex table for the handover comparison and a .csv file with the handover comparison results, a file with the latex table and a .txt file with the raw output of the handover analysis.
