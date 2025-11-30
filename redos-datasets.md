# ReDoS datasets

A collection of ReDoS datasets to test for all linear-engines I can find.

| Name           | URL                                             | Paper                                                                            | Quality | Format    |
|----------------|-------------------------------------------------|----------------------------------------------------------------------------------|---------|-----------|
| Revealer       | https://github.com/cuhk-seclab/Revealer         | https://www.computer.org/csdl/proceedings-article/sp/2021/893400b063/1t0x8WDjGGk | Great   | JSON list |
| RXXR2          | https://github.com/superhuman/rxxr2             |                                                                                  | Fine    | Text      |
| RegexEval      | https://github.com/s2e-lab/RegexEval            | https://s2e-lab.github.io/paper/research/dataset/llm/icse-nier-2024/             | Great   | JSON list |
| Rat            | https://github.com/phreppo/rat                  | https://link.springer.com/chapter/10.1007/978-3-031-10363-6_6                    | Fine    | OCaml     |
| RegexScalpel   | https://github.com/iscas-depso/RegexScalpel     | https://www.usenix.org/conference/usenixsecurity22/presentation/li-yeting        | Fine    | Text      |
| Tour De Dource | https://github.com/softwarekitty/tour_de_source |                                                                                  | Great   | Text      |


Some of the repositories I looked through to find datasets did not include data. Those were put into this second table.

| Name                | URL                                             | Paper                                              | Quality | Format           |
|---------------------|-------------------------------------------------|----------------------------------------------------|---------|------------------|
| ReDoS Study         | https://github.com/s2e-lab/redos-study          | https://dl.acm.org/doi/abs/10.1145/3643916.3644424 | Bad     | Not found        |
| Vuln Regex Detector | https://github.com/davisjam/vuln-regex-detector |                                                    | Bad     | Too few examples |
| ReScue              | https://github.com/2bdenny/ReScue               |                                                    | Bad     | Not found        |

I thought the "ReDoS Study" would yield a good dataset but the data included are conversations about ReDoS on public forums.
