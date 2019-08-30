# nflxprofile

`nflxprofile` is a profiling/tracing format implemented using 
[Protocol Buffers](https://developers.google.com/protocol-buffers/). The goal of
the format is to provide a compact yet complete and performant way to store
profiling and tracing events, which can later be used to generate Flame Graphs,
heat maps and other visualizations. It was first introduced in 
[FlameScope](https://medium.com/netflix-techblog/trace-event-chrome-and-more-profile-formats-on-flamescope-5dfe9df5dfa9).

This repository is the source-of-truth for the format. It also contains a 
[Python library](https://pypi.org/project/nflxprofile/) to make it easier to
use this format in Python projects.
