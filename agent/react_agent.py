import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain.agents import create_agent
from agent.tools.agent_tools import rag_summarize
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch

from model.factory import chat_model
from utils.prompt_loader import load_system_prompt


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=[rag_summarize],
            middleware=[monitor_tool, log_before_model, report_prompt_switch]
        )
    
    def execute_stream(self,query:str):
        input_dict={
            "messages":[
                {"role":"user","content":query}
            ]

        }
        for chunk in self.agent.stream(input_dict,stream_mode="values",context={"report":False}):
            latest_message=chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip()+"\n"
if __name__=="__main__":
    react_agent=ReactAgent()
    for chunk in react_agent.execute_stream("我的车空调不制冷怎么排查"):
        print(chunk,end="",flush=True)






