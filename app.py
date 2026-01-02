import pandas as pd
import streamlit as st 
import os

st.write("Si jeni te gith")

st.write(True)
press_me = st.button("Press me")
print(press_me)
#st.image("static/alb.png", caption="Mein Logo")
st.image(os.path.join(os.getcwd(),"static","alb.png"),caption="Shqiperia")


#each rerun care of the states of the botton for example

# st.write("Si jeni")
# st.write("Si jeni")
# st.write("Si jeni")
# st.write("Si jeni")
