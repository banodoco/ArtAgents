# Explore E3: Wan2GP headless driving contract reconstruction
Read .oracle/northstar.md + .oracle/agent_goal.md + grok-reports/worker-wgp-report.md first. The wgp report exists there now.
Question: reconstruct the headless driving contract precisely — entry points (wgp.generate_video/load_models), cwd/sys.path requirements, config schema (wgp_config.json keys), preset mapping (TASK_TYPE_TO_MODEL), checkpoint layout/download behavior, and the five-gate decomposition for upgrades (what each gate tests mechanically). Note what CANNOT be verified without CUDA and mark it.
Report: ranked findings <300 words with file/repo evidence + the five gates concretely defined.
