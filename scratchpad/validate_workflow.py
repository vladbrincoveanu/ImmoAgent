import yaml

d = yaml.safe_load(open(".github/workflows/coop-fast-poll.yml"))
on = d[True]  # PyYAML parses the bare `on:` key as the boolean True
print("YAML OK")
print("triggers:", sorted(on.keys()))
print("cron:", on["schedule"])
print("dispatch types:", on["repository_dispatch"]["types"])
print("timeout-minutes:", d["jobs"]["poll"]["timeout-minutes"])
print("job env:", d["jobs"]["poll"]["env"])
print("steps:", len(d["jobs"]["poll"]["steps"]))
print("last step run:", d["jobs"]["poll"]["steps"][-1]["run"].strip())
