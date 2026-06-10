Meeting: 06-09-2026

## Graphing

Always want labels to be uniform (in some way)

- The Y axis isn't linear
- The X axis should not be in buckets

Y axis seems to be 25,000 but not exactly.

## Graph Choice

Regex choice is more important than regex length

Don't split into small medium and large. Instead, it should be known bad, low complexity, high complexity.

Plotting Regex size doesn't make a lot of sense.

"We show where regex size tends to fall"

The Regex size is not that interesting.

We can increase the input length to 5 million.

Try to make a fast version and a slow version. Have a quick mode: test half the things, half the langs, half the timeout.

Go down to 50,000 or 100,000 for each bucket. We are testing things that are too small. Nothing timed out in Rust.

"Don't want Regex size that we plot at all"

1. Vary input size
2. Average runtime

Drop the three regex classes down to two: Bad Regexes, Random Regexes (Lucas' tool). Not getting much signal size from regex. Skip out on the complex one.

Results for bad regexes - results for random regexes.

The engine is more important than the language.

Drop the medium and large ones, merge them together, etc.

Pump up the running time so the running time takes over base overhead of the language.

The scatter plot should be split up by engine.

RQ: How do engines affect running time?

"Language isn't uninteresting, it's just not the primary RQ"

Get one set of plots with all engines, marked by engine and not language as a scatter plot.

Three figures:

1. Simple line plot (already have it) showing 10 engines on a single evil Regex (`test_27_performance.png`)

What it does: It shows that some engines is vulnerable and some are not.

"The fun exponential curve"

2. Scatter plot input size x runtime, by engine (`image.png`)
- TODO: correct the input size increment. Increment of powers of 10
- scale: 0, 10-100 million
- 1, 10, 100, 1,000, 10,000 ... 10,000,000
- two plots: 1 for known bad, 1 for random (low complexity freak)

Scatter plot vs. line graph? Data that jumps -> scatter plot. For an 
average, a line graph makes more sense. Generate both and pick your
favorite based on the results.

Scatter plot => all points plotted
Line graph => average of the data

Remove the four non-linear time engines to get more subtle engines.

"Zooming in on the linear time ones"

3. (`redos-time.png`)

--- Second Part ---

Timeline:

Due June 14th

Human aspect part: What would people consider to be a redos in practice?

Argue there is a human element to how a developer expects a Redos to perform.

Prepare an email draft / linked in post draft:

2 (maybe 3) questions:

Imagine you were writing server backend code and had a Regex run for each endpoint hit.
For each question, assume typical server under typical industry circumstances.

1. How long should a Regex take before it's *possibly* a security issue to your server
(Where is the boundary for a security issue)

Range: 0 ms to 1 minute

2. How long should a Regex take before it's *certainly* a security issue to your server
(Where is the boundary for a security issue)

Range: 0 ms to 1 minute

3. In normal circumstances, how long do you think a good regex takes on average
(See if people have good regex intuition)

Range: 0 ms to 1 minute

^^ Caleb likes this control for testing if people who have good intuition.

Provide optional comments so they can make assumptions, etc.

Draft it and send it to Caleb THIS EVENING to post.

Find a few names from papers, tools, and people I know who do security

Nathaniel Rogalskyj
Wes Hardaker
David Huska
Ben Dicken

Intro - Caleb
Methods - 
Related Work

I write a section and send it for review, then I start working on the next part instantly.

Scan for: Linear, Matching, Non Backtracking, ReDoS.
Maybe backreferences, lookaround, lookahead

You're not going to be able to read all of these related papers but try to put them into categories to see which ones you'll need to look at later.

Three categories of papers, each on paragraph:

1. Non-backtracking and linear time matches

Who has built linear time matches?

Use the BFS search

2. ReDoS papers

Search for ReDoS to try to find practical surveys

Who has studied ReDoS before?

3. (Maybe we need it, maybe we don't)

...

Make a table of the most important papers that you know about and columns for their specific
differences. Column e.g. "is it linear time", "do they study redos on string len?", "redos on regex len?" Put citations directly into the document.
