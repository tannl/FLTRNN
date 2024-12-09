# FLTRNN:Faithful Long-Horizon Task Planning for Robotics with Large Language Models

### Environment Dependency
The experimental environment is virtualhome, and the virtualhome version of our experiment is 2.2.5. For the installation and configuration of virtualhome, please refer to the official documentation:
http://virtual-home.org/tools/explore.html
https://github.com/xavierpuigf/virtualhome


### Run
Run the program by executing `sh scripts/inference.sh` in the behavior_cloning directory.


### control flags:
```
if_gpt = True   # use the gpt api to perform task planning
if_exe_all_action = True  #execute the complete plan after the generation is completed, or to execute while generating.
```

Before execution, you need to add your own api-key in gpt_policy.py
```
api_key = [api-key1, api-key2]
api_key_num = 2
```

### Related code directory
```
inference.sh： some control parameters
gpt_policy.py： Interaction interface files related to GPT
interactive_interface_fn： main process function
/checkpoint/LID-Text/interactive_eval： log files


```
