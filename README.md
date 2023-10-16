# FLTRNNL

### 运行
在behavior_cloning目录下执行以运行程序
`sh scripts/inference.sh`

跟GPT相关的交互接口文件`gpt_policy.py`
主流程函数 `interactive_interface_fn`
control flags:
```
if_gpt = False   # 是否使用gpt交互接口来执行任务规划
if_exe_all_action = True  #是否生成结束后再执行完整规划，相对应的是边生成边执行
```

执行之前需要在gpt_policy.py中添加自己的api-key
```
api_key = [api-key1, api-key2]
api_key_num = 2
```
