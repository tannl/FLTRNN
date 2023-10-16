import random
import time

import requests
import json
import re
import json
import sys
import openai
import os
from sim_compute import Similarity
from memory_graph import MemoryGraph

sys.path.append('../virtualhome')
from simulation.unity_simulator import comm_unity as comm_unity


api_key = []


api_key_num = 0


# 单步对话
def getChatResponse(ask, api_key='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'):

    openai.api_key = api_key
    os.environ["http_proxy"] = "127.0.0.1:7890"
    os.environ["https_proxy"] = "127.0.0.1:7890"
    while True:
        try:
            res = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {'role': 'user', 'content': ask}
                ],
            )

            return res
        except openai.error.APIError as e:
            print(f"Exception caught: {e}")


def split_goal(log, task_goal):
    with open('subgoal_demo.txt', 'r') as file:
        exampleTask = file.read()
    file.close()

    Prompt = "Please split the task goal, there are some examples: \n" + exampleTask + "Task goal:" + task_goal
    response = getChatResponse(Prompt)
    context = response['choices'][0]['message']['content']

    log.info(context)
    pattern_count = r"subgoal{.+?}"

    subgoal_count = len(re.findall(pattern_count, context))
    log.info(f"Number of subgoals: {subgoal_count}")
    # 提取子目标内容
    pattern_subgoal = r"subgoal{(.+?)}"
    subgoals = re.findall(pattern_subgoal, context)
    return subgoals, subgoal_count


sc = Similarity()




# def a class as a gpt policy
class GPTPolicy:
    def __init__(self, logging):

        self.graph = None
        self.memory_graph = MemoryGraph(None)
        self.task_goal = None
        self.split_task_goal = None
        self.split_task_goal_num = 0
        self.goal_exe_index = 0
        self.completed_goal = ''
        self.task_obj = []  # 记录任务中所涉及到的obj
        self.exec_action_lists = []
        self.exec_action_index = 0  # the index of the action to be executed
        self.api_index = 0
        self.goal_objs_loc = None
        self.logging = logging
        self.sc = Similarity()

    def set_graph(self, graph):
        self.graph = graph
        self.memory_graph.set_graph(graph)

    def set_goal(self, lid_goals):
        task_goal = ''
        goal_objs = []  # 目标物品
        # translate the env_task_goal_write to natural language
        for k, v in lid_goals.items():
            if v > 0:
                obj_id = int(k.split('_')[-1])
                obj_name = [node['class_name'] for node in self.graph['nodes'] if node['id'] == obj_id][0]
                # 判断当前obj是否在goal中已存在避免重复存储
                have_exist_in_goal = False
                for id, name in goal_objs:
                    if id == obj_id:
                        have_exist_in_goal = True
                if not have_exist_in_goal:
                    goal_objs.append((obj_id, obj_name))
                # 判断当前goal_obj在task_obj中是否已存储
                have_exist = False
                for id, name in self.task_obj:
                    if id == obj_id and obj_name == name:
                        have_exist = True
                if not have_exist:
                    self.task_obj.append((obj_id, obj_name))
                task_goal += k.replace(k.split('_')[-1], obj_name + "(id:{})".format(obj_id)) + ': ' + str(v) + ','
                # 获取相关obj
                name = str(k.split('_')[-2])
                for node in self.graph['nodes']:
                    if node['class_name'] == name:
                        goal_objs.append((node['id'], name))

        print('[INFO] task goal GPT version:', task_goal)
        self.task_goal = task_goal
        # print('[INFO] goal obj:')
        # find the location of the goal objects
        goal_objs_loc = []  # 带有地点的目标物品
        for obj_id, obj_name in goal_objs:
            from_obj_edges = [edge for edge in self.graph['edges'] if edge['from_id'] == obj_id]
            for edge in from_obj_edges:
                if edge['relation_type'] == 'INSIDE':
                    to_obj_id = edge['to_id']
                    to_obj_name = [node['class_name'] for node in self.graph['nodes'] if node['id'] == to_obj_id][0]
                    self.task_obj.append((to_obj_id, to_obj_name))
                    goal_objs_loc.append(('%s(id:%d)' % (obj_name, obj_id), edge['relation_type'],
                                          '%s(id:%d)' % (to_obj_name, to_obj_id)))

        # print('[INFO] goal obj loc:', list(set(goal_objs_loc)))
        self.goal_objs_loc = goal_objs_loc
        self.task_goal = task_goal

    def get_goal_obj_message(self, task):
        # closed_microwave(id:158): 1,turnon_microwave(id:158): 1,on_milk_kitchentable(id:123): 3,inside_pancake_microwave(id:158): 1,
        self.graph = self.memory_graph.graph
        goals = task.split(',')
        need_grab_obj = []
        goal_objs_loc = []
        need_put_obj = []
        need_get_obj = []
        reason_message = []
        for goal in goals:
            obj = goal.split('_')
            for name in obj:
                for node in self.graph['nodes']:
                    if node['class_name'] == name:
                        need_grab_obj.append((node['id'], name))
                pattern = r'(\w+)\(id:(\d+)\)'
                matches = re.findall(pattern, name)
                if matches:
                    id_ = int(matches[0][1])
                    name_ = matches[0][0]
                    id_list = [id_ for id_, name_ in need_put_obj]
                    if id_ not in id_list:
                        need_put_obj.append((id_, name_))

        for obj_id, obj_name in need_grab_obj:
            reason_message.append('%s(id:%d)' % (obj_name, obj_id))
            from_obj_edges = [edge for edge in self.graph['edges'] if edge['from_id'] == obj_id]
            for edge in from_obj_edges:
                if edge['relation_type'] == 'INSIDE':
                    to_obj_id = edge['to_id']
                    to_obj_name = [node['class_name'] for node in self.graph['nodes'] if node['id'] == to_obj_id][0]
                    goal_objs_loc.append(('%s(id:%d)' % (obj_name, obj_id), edge['relation_type'],
                                          '%s(id:%d)' % (to_obj_name, to_obj_id)))
                    id_list = [id_ for id_, name_ in need_get_obj]
                    if to_obj_id not in id_list:
                        need_get_obj.append((to_obj_id, to_obj_name))
        obj_state = ''
        for obj_id, obj_name in need_put_obj:
            state = ''
            reason_message.append('%s(id:%d)' % (obj_name, obj_id))
            for node in self.graph['nodes']:
                if node['id'] == obj_id:
                    state = node['states']
                    break
            if state != '':
                if 'OPENED' in state:
                    obj_state += '{}(id:{})\'s states are '.format(obj_name, obj_id)
                    obj_state += 'opened,'
                if 'CLOSED' in state:
                    obj_state += '{}(id:{})\'s states are '.format(obj_name, obj_id)
                    obj_state += 'closed,'
                if 'ON' in state:
                    obj_state += 'on,'
                if 'OFF' in state:
                    obj_state += 'off,'
        for obj_id, obj_name in need_get_obj:
            state = ''
            for node in self.graph['nodes']:
                if node['id'] == obj_id:
                    state = node['states']
                    break
            if state != '':
                if 'OPENED' in state:
                    obj_state += '{}(id:{})\'s state is '.format(obj_name, obj_id)
                    obj_state += 'opened,'
                if 'CLOSED' in state:
                    obj_state += '{}(id:{})\'s state is '.format(obj_name, obj_id)
                    obj_state += 'closed,'

        state_memory = str(list(set(goal_objs_loc))) + ' and ' + obj_state
        return state_memory

        # return str(reason_message)

    def get_subtask_message(self, reason_subtask):
        pattern = r"id:(\d+)"
        ids = re.findall(pattern, reason_subtask)
        self.graph = self.memory_graph.graph
        goal_objs_loc = []
        need_get_obj = []
        obj_state = ''
        for id_ in ids:
            id_ = int(id_)
            from_obj_edges = [edge for edge in self.graph['edges'] if edge['from_id'] == id_]
            to_obj_edges = [edge for edge in self.graph['edges'] if edge['to_id'] == id_]
            nodes = [node for node in self.graph['nodes'] if node['id'] == id_]
            if nodes:
                obj_name = nodes[0]['class_name']
            else:
                return False
            for edge in from_obj_edges:
                if edge['relation_type'] == 'INSIDE':
                    to_obj_id = edge['to_id']
                    to_obj_name = [node['class_name'] for node in self.graph['nodes'] if node['id'] == to_obj_id][0]
                    goal_objs_loc.append(('%s(id:%d)' % (obj_name, id_), edge['relation_type'],
                                          '%s(id:%d)' % (to_obj_name, to_obj_id)))
                    ids.append(to_obj_id)
                    print(ids)
            state = ''
            for edge in to_obj_edges:
                if edge['relation_type'] == 'HOLDS_RH':
                    obj_state += '{}(id:{}) in your hand,'.format(obj_name, id_)
            for node in self.graph['nodes']:
                if node['id'] == id_:
                    state = node['states']
                    break
            if state != '':
                if 'OPENED' in state:
                    obj_state += '{}(id:{})\'s states are '.format(obj_name, id_)
                    obj_state += 'opened,'
                if 'CLOSED' in state:
                    obj_state += '{}(id:{})\'s states are '.format(obj_name, id_)
                    obj_state += 'closed,'
                if 'ON' in state:
                    obj_state += 'on,'
                if 'OFF' in state:
                    obj_state += 'off,'
        if obj_state:
            state_memory = str(list(set(goal_objs_loc))) + ' and ' + obj_state
        else:
            state_memory = str(list(set(goal_objs_loc)))
        return state_memory

    # get top k demonstration
    def top_k_demo(self, K, mod, task_goal):
        # -----------------demo build---------------------------
        exampleTask = ''
        with open('./subgoal_demo_set.txt', 'r') as f:
            demo_set_temp = f.read()
        f.close()

        # 提取每个task的字符串信息
        demo_set = demo_set_temp.split('task_id')[1:]
        demo_list = []
        for demo in demo_set:
            # 提取task_id
            task_id = demo.split('\n')[0]
            demo = demo.replace('-', '').replace(task_id, '')
            demo_list.append(demo)
        if mod == 'sim':
            scores = []
            for index, task in enumerate(demo_list):
                task_desc = task.split('#The task goal:')[1].split('\n')[0]
                sim_score = self.sc.sim_compute(task_desc, task_goal)
                scores.append({'id': index, 'score': sim_score, 'desc': task_desc, 'demo': task})

            def get_score(obj):
                return obj['score']

            scores = sorted(scores, key=get_score, reverse=True)

            topk = scores[:K]
            # print('[INFO] sampled Exp:',top10)
            self.logging.info('------- Sim Demo Sampling ------')
            self.logging.info('test task' + task_goal)
            self.logging.info('demo tasks:')
            for exp in topk:
                self.logging.info(exp['desc'])
            self.logging.info('----------------------------')
            # print(scores[:30])
            examplelist = [score['demo'] for score in topk]
        elif mod == 'random':
            self.logging.info('------- Random Demo Sampling ------')
            self.logging.info('test task' + task_goal)
            self.logging.info('demo tasks:')
            random_demo = random.sample(demo_list, K)
            for task in random_demo:
                task_desc = task.split('#The task goal:')[1].split('\n')[0]
                self.logging.info(task_desc)
            examplelist = random_demo
        else:
            return None
        for demo in examplelist:
            exampleTask += demo

        return exampleTask

    def demo_build(self, K, task_goal):
        # -----------------demo build---------------------------
        exampleTask = ''
        with open('./subgoal_demo_set.txt', 'r') as f:
            demo_set_temp = f.read()
        f.close()

        # 提取每个task的字符串信息
        demo_set = demo_set_temp.split('task_id')[1:]
        demo_list = []
        for demo in demo_set:
            # 提取task_id
            task_id = demo.split('\n')[0]
            demo = demo.replace('-', '').replace(task_id, '')
            demo_list.append(demo)

        scores = []
        for index, task in enumerate(demo_list):
            task_desc = task.split('#The task goal:')[1].split('\n')[0]
            sim_score = self.sc.sim_compute(task_desc, task_goal)
            scores.append({'id': index, 'score': sim_score, 'desc': task_desc, 'demo': task})

        def get_score(obj):
            return obj['score']

        scores = sorted(scores, key=get_score, reverse=True)
        top_one = scores[:1]
        simdemo = top_one[0]['demo']
        demo = random.sample(demo_list, K - 1)
        demo.append(simdemo)

        self.logging.info('------- Demo Sampling ------')
        self.logging.info('test task:' + task_goal)
        # self.logging.info('sim demo task  ' + top_one[0]['desc'])
        self.logging.info('sample demo task  ')
        for task in demo:
            task_desc = task.split('#The task goal:')[1].split('\n')[0]
            self.logging.info(task_desc)
            exampleTask += task
        return exampleTask

    def generate_plan_old(self):
        task_goal = self.task_goal
        task_goal, i = split_goal(self.logging, self.task_goal)
        # --------------------------------
        # Step 1: construct the prompt
        # --------------------------------
        rulePrompt = '\n# remember if the key object INSIDE kitchencabinet, you should open the kitchencabinet first ' \
                     'or the key object INSIDE room, you should walk to the room' \
                     'and different id represent different items, so note the id number.' \
                     'remember you should grab only one item at a time and ' \
                     'you can not open a cabinet that has been opened\n'

        actionPrimitives = "from actions import " \
                           "walk <obj>, grab <obj>, switchon <obj>, switchoff <obj>, " \
                           "open <obj>, close <obj>, " \
                           "turnto <obj>, drink <obj>, putin <obj> <obj>, putback <obj> <obj>\n"

        with open('demo.txt', 'r') as file:
            exampleTask = file.read()
        file.close()

        # nextPrompt = "#The task goal: " + task_goal + "\ndef task():"

        context = ""
        for task in task_goal:
            envPrompt = '\n# remember the key object locations and states: ' + self.get_goal_obj_message(task) + '\n'
            nextPrompt = "#The task goal: " + task + "\ndef task():"
            self.logging.info('[INFO] env Prompt is :' + envPrompt)
            fullPrompt = actionPrimitives + rulePrompt + "There are some examples: \n" + exampleTask + envPrompt
            final_prompt = fullPrompt + nextPrompt
            if self.api_index < api_key_num - 1:
                self.api_index += 1
            response = getChatResponse(final_prompt, api_key[self.api_index])
            context = response['choices'][0]['message']['content'] + '\n'
            self.logging.info("=====================prompt=========================\n" + final_prompt)
            self.logging.info("=====================generate context=========================\n" + context)
            self.context_analysis(context)

    def generate_plan(self, task):
        rulePrompt = '# remeber if the key object INSIDE kitchencabinet, you should open the kitchencabinet first ' \
                     'or the key object INSIDE room, you should walk to the room' \
                     'and different id represent different items, so note the id number.' \
                     'remeber you should grab only one item at a time and ' \
                     'you can not open a cabinet that has been opened\n'

        actionPrimitives = "from actions import " \
                           "walk <obj>, grab <obj>, switchon <obj>, switchoff <obj>, " \
                           "open <obj>, close <obj>, " \
                           "turnto <obj>, drink <obj>, putin <obj> <obj>, putback <obj> <obj>\n"

        exampleTask = self.top_k_demo(3, 'sim', task)
        long_memory = actionPrimitives + rulePrompt + "# The total task goal: " + self.task_goal + \
                      "\n# The completed task goal: " + self.completed_goal

        short_memory = "There are some examples: " + exampleTask + '# remember the key object locations and states: ' \
                       + self.get_goal_obj_message(task) + '\n'
        full_prompt = "long_memory: \n" + long_memory + "\n\nshort_memory: \n" \
                      + short_memory
        next_prompt = "\n#The task goal: " + task + "\ndef task():"
        final_prompt = full_prompt + next_prompt
        if self.api_index < api_key_num - 1:
            self.api_index += 1
        response = getChatResponse(final_prompt, api_key[self.api_index])
        context = response['choices'][0]['message']['content'] + '\n'
        self.logging.info("=====================prompt=========================\n" + final_prompt)
        self.logging.info("=====================generate context=========================\n" + context)
        self.context_analysis(context)
        self.completed_goal += task + ','

    def generate_prog_plan(self, task):
        rulePrompt = '\n# remeber if the key object INSIDE kitchencabinet, you should open the kitchencabinet first ' \
                     'or the key object INSIDE room, you should walk to the room ' \
                     'and different id represent different items, so note the id number.' \
                     'remember you should grab only one item at a time and ' \
                     'you can not open a cabinet that has been opened\n'

        actionPrimitives = "from actions import " \
                           "walk <obj>, grab <obj>, switchon <obj>, switchoff <obj>, " \
                           "open <obj>, close <obj>, " \
                           "turnto <obj>, drink <obj>, putin <obj> <obj>, putback <obj> <obj>\n"

        with open('prog_examples.txt', 'r') as file:
            exampleTask = file.read()
        file.close()

        env_prompt = "\n# remember the key object locations and states: " + self.get_goal_obj_message(task) + '\n'
        full_prompt = actionPrimitives + rulePrompt + "\n#There are some examples: \n" + exampleTask + env_prompt
        next_prompt = "\n#The task goal: " + task + "\ndef task():"
        final_prompt = full_prompt + next_prompt
        if self.api_index < api_key_num - 1:
            self.api_index += 1
        response = getChatResponse(final_prompt, api_key[self.api_index])
        context = response['choices'][0]['message']['content'] + '\n'
        self.logging.info("=====================prompt=========================\n" + final_prompt)
        self.logging.info("=====================generate context=========================\n" + context)
        self.context_analysis(context)

    def generate_PR_plan(self, task):

        reasoner_info = 'Now you are a task planning assistant, responsible for inferring the execution steps of a task.' \
                        'You should mimic the provided examples and, based on the task objectives' \
                        ', understand the total task goal first, generate the next sub-task. \n'

        planner_info = '\nNow you are a task planning assistant. You should mimic the examples I provide and generate ' \
                       'a sequence of actions based on the target instructions and environmental information. ' \
                       'Pay attention to the task objectives and environmental information.\n'
        planner_rule = "And remember if the key object INSIDE kitchencabinet, you should open the kitchencabinet first," \
                       "or the key object INSIDE room, you should walk to the room,and different id represent " \
                       "different items, so note the id number.Remember you should grab only one item at a time and" \
                       "you can not open a cabinet that has been opened.\n"

        with open('planner_demo.txt', 'r') as file:
            exampleTask = file.read()
        file.close()
        planner_examples = "\nThere are some examples: \n" + exampleTask + "\n Imitate these examples to generate an action list.\n"

        with open('reason_demo_v2.txt', 'r') as file:
            exampleTask = file.read()
        file.close()
        reasoner_examples = "\nThere are some examples: \n" + exampleTask + "\nImitate these examples to generate a step-by-step plan.\n"
        reasoner_task = "\nTask goal: " + task
        context = ''
        i = 0
        reasoner_prompt = reasoner_info + reasoner_examples + reasoner_task + "\nReason task lists: \n"
        res = getChatResponse(reasoner_prompt)
        reasoner = res['choices'][0]['message']['content']
        self.logging.info("=================reasoner==================\n" + reasoner_task + "\nReasoner: \n"
                          + reasoner + "\n")
        reason_tasks = reasoner.split('\n')

        for reason_subtask in reason_tasks:
            obj_message = self.get_goal_obj_message(task)
            planner_prompt = planner_info + planner_examples + "\nNow the task is: " + reason_subtask + \
                             "\nremember the key object locations and states: " + obj_message + "\nPlanning action lists:"
            if i < api_key_num - 1:
                i += 1
            else:
                i = 0
            res = getChatResponse(planner_prompt, api_key[i])
            action_list = res['choices'][0]['message']['content']
            self.logging.info(
                "=================planner==================\n" + "\nNow the task is: " + reason_subtask + \
                             "\nremember the key object locations and states: " + obj_message + "\nPlanner: \n" + action_list)
            if self.context_analysis(action_list) is False:
                return None
            context += action_list
            time.sleep(10)


    def generate_recurrent_plan(self):

        self.split_task_goal, self.split_task_goal_num = split_goal(self.logging, self.task_goal)
        for task in self.split_task_goal:
            self.generate_plan(task)
        self.logging.info('--------final action list--------\n')
        for action in self.exec_action_lists:
            self.logging.info(action)
        # self.context_analysis(total_context)

    def context_analysis(self, context):
        # 解析生成的文本plan，并执行
        lines = context.split('\n')
        id_list = []  # 用于过滤重复打开动作
        for line in lines:
            # 定义正则表达式模式
            line.replace(" ", "")
            pattern = r"(walk|find|open|grab|close|switchon)\('(\w+)\(id:(\d+)\)'\)"
            match = re.match(pattern, line)
            if match:
                action = match.group(1)
                if action == 'find':
                    action = 'walk'
                item_name = match.group(2)
                item_id = match.group(3)
                action_script = "[{}] <{}> ({})".format(action, item_name, item_id)
                '''
                if action == 'open':
                    if item_id not in id_list:
                        id_list.append(item_id)
                        self.exec_action_lists.append(action_script)
                else:
                '''
                self.exec_action_lists.append(action_script)
                if self.memory_graph.simulate_action(action_script) is False:
                    return False
            pattern = r"(putback|putin)\('(\w+)\(id:(\d+)\)', '(\w+)\(id:(\d+)\)'\)"
            match = re.match(pattern, line)
            if match:
                action = match.group(1)
                item1_name = match.group(2)
                item1_id = match.group(3)
                item2_name = match.group(4)
                item2_id = match.group(5)
                action_script = "[{}] <{}> ({}) <{}> ({})".format(action, item1_name, item1_id, item2_name, item2_id)
                self.exec_action_lists.append(action_script)
                if self.memory_graph.simulate_action(action_script) is False:
                    return False

    def get_action_from_chatgpt(self):
        action_obj_str = ''
        if self.exec_action_index >= len(self.exec_action_lists):
            return action_obj_str
        action_obj_str = self.exec_action_lists[self.exec_action_index]
        self.exec_action_index += 1
        return action_obj_str
