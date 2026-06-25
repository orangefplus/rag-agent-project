import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import time
from rag_agent_project.agent.react_agent import ReactAgent

st.title("车载智能客服系统")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()
if "messages" not in st.session_state:
    st.session_state["messages"] = []
for message in st.session_state["messages"]:
    st.chat_message(message["role"]).write(message["content"])
    
prompt=st.chat_input()
if prompt:
    response_messages=[]
    st.chat_message("user").write(prompt)
    st.session_state["messages"].append({"role":"user","content":prompt})
    with st.spinner("思考中..."):
        res_stream=st.session_state["agent"].execute_stream(prompt)
        def capture(generator,cache_list):
            for chunk in generator:
                cache_list.append(chunk)
                for char in chunk:
                    time.sleep(0.01)
                    yield char

        st.chat_message("assistant").write_stream(capture(res_stream,response_messages))
        st.session_state["messages"].append({"role":"assistant","content":response_messages[-1]})
        st.rerun()



