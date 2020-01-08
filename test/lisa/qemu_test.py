import logging
import os
from lisa.trace import FtraceCollector, Trace
from lisa.utils import setup_logging
from lisa.target import Target, TargetConf
from lisa.wlgen.rta import RTA, Periodic
from lisa.datautils import df_filter_task_ids
import pandas as pd

setup_logging()
target = Target.from_one_conf('conf/lisa/qemu_target_default.yml')
#target = Target.from_default_conf()

rtapp_profile = {}
tasks = []
for cpu in range(4):
    tasks.append("tsk{}-{}".format(cpu,cpu))
    rtapp_profile["tsk{}".format(cpu)] = Periodic(duty_cycle_pct=50, duration_s=120) 

wload = RTA.by_profile(target, "experiment_wload", rtapp_profile)

ftrace_coll = FtraceCollector(target, events=["sched_switch"])
trace_path = os.path.join(wload.res_dir, "trace.dat")
with ftrace_coll:
    wload.run()

ftrace_coll.get_trace(trace_path)
trace = Trace(trace_path, target.plat_info, events=["sched_switch"])

# sched_switch __comm  __pid  __cpu  __line prev_comm  prev_pid  prev_prio  prev_state next_comm  next_pid  next_prio
df = trace.df_events('sched_switch')[['next_pid', 'next_comm', '__cpu']]

def analize_task_migration(task_id, ddf):
    start = ddf.index[0]
    stop = min(ddf.index[1] + 1.0, df.index[-1])
    start_cpu = ddf['__cpu'].values[0]
    stop_cpu = ddf['__cpu'].values[1]
    _df = df[start:stop][ df[start:stop]['__cpu'] == start_cpu ]
    print("Task {} migrated from CPU {} to CPU {}\n".format(task_id, start_cpu, stop_cpu))
    print(_df.to_string(max_cols = 64) + "\n")

for task in tasks:
    task_id = trace.get_task_id(task, update=False)
    _df = df_filter_task_ids(df, [task_id], pid_col='next_pid', comm_col='next_comm')
    ddf = _df.drop_duplicates(subset='__cpu', keep='first', inplace=False)
    print("******************  sched_switch {} ********************\n {} \n".format(task , ddf.to_string(max_cols = 64)))
    if len(ddf.index) > 1:
        analize_task_migration(task_id, ddf)



