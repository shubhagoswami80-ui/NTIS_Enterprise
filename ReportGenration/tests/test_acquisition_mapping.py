from pathlib import Path
import importlib.util

p=Path(__file__).resolve().parents[1]/"pece_xhr_golive_engine.py"
spec=importlib.util.spec_from_file_location("engine",p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

assert len(m.REPORT_HEADERS)==37
assert len(m.PACKED_MAP)==6

row=[
"15:40","23500.00:#17CE06","16:0.07","18.7:0.08","23397.92","11.02",885,277037,
"-4959:-1.76:red","229:0.08:",1346074,1136334,"-209740:red","28177:red",
"29060:#4CAF50","0.84:","1132688.2307692:#FFEBEB","1150857.3076923:green",
"1.02:#4CAF50","18170:green",0.8,"53295:#FFEBEB","74333:green",3.96,6.54,
"1.39:#4CAF50","21038:green",0.92,"-1608:-0.14","797:0.07",2405
]
mapped=m._map_xhr_row(row)
assert mapped[0]=="15:40"
assert mapped[1]==23500.0
assert mapped[2]==16.0 and mapped[3]==0.07
assert mapped[4]==18.7 and mapped[5]==0.08
assert mapped[10]==-4959.0 and mapped[11]==-1.76
assert mapped[12]==229.0 and mapped[13]==0.08
assert mapped[32]==-1608.0 and mapped[33]==-0.14
assert mapped[34]==797.0 and mapped[35]==0.07
assert mapped[36]==2405
assert all(not (isinstance(x,str) and (":red" in x or ":green" in x or "#" in x)) for x in mapped)
print("PASS: PE/CE 31-field XHR -> complete 37-column clean report mapping")
