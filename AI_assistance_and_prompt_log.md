# AI Assistance Disclosure and Prompt Log

**Project:** Insurance Claims Synthetic Data Generator
**Repository:** https://github.com/SaiMokshagna/Insurance-claims-synthetic-data
**AI tool:** Claude (Anthropic), used in the claude.ai chat, in one long conversation of about 40 of my messages
**Why this document exists:** the assignment asks for the prompts used, and I want the record to be accurate about what I did and what the AI did.

## 1. Summary

I used an AI assistant throughout this project. I set the working rules in my first prompt, approved the plan and its assumptions, ran every command on my own machine (Windows, PowerShell, Python 3.11.9, VS Code, Git), pasted the results back, reported errors, and made the setup and Git decisions. The AI wrote the code, tests, data dictionary, README and helper scripts, explained decisions, and found the root cause of the errors I reported. The conversation itself is the primary record. A full transcript is available on request.

## 2. Who did what

| Area | What I did | What the AI did |
|---|---|---|
| Direction | Wrote the starting prompt: mentor role, fresher-friendly stack, no unnecessary complexity, real working integrations, test each milestone, explain decisions, no code before the plan | Followed those rules in every reply |
| Problem analysis | Provided the company's problem statement, reviewed the analysis, and approved it by replying "proceed" | Interpreted the brief, proposed the "generator-first" approach, listed assumptions, stack and architecture |
| Code, tests, docs | Created the files, pasted the code, and applied each edit in my project folder | Wrote the code for milestones M0 to M9, the tests, data dictionary, README and scripts |
| Running and checking | Ran the tests, the generator, the checksum and reproducibility scripts, and the demo; pasted the outputs and asked whether they were correct | Read each output, said whether it was correct, and explained the numbers |
| Debugging | Reported each error with the full output | Identified the root cause and gave the fix |
| Git and GitHub | Initialised the repository, created the GitHub repo, chose its name, committed, pushed, and cloned it to test | Gave the commands and explained them |
| Final review | Asked for a review of weaknesses before submitting | Listed gaps and a plan to close them |

## 3. My starting prompt

My first message gave the AI a mentor role (a senior AI engineer helping a fresher applying for the Associate AI Forward Deployed Engineer role) and attached the company's problem statement. It set these rules:

* Recommend an intermediate-level stack that a fresher can learn, debug and explain.
* Avoid microservices, excess abstraction and tools that do not solve the problem.
* Treat the problem statement as the source of truth; do not invent requirements.
* Analyse the problem, scope, stack and architecture before writing any code.
* Then build incrementally, with exact commands, tests after each milestone, root-cause diagnosis of errors, and no faked integrations.
* Be honest about limits, costs and risks, and do not claim anything guarantees a shortlist.

(The full text is the first message of the conversation.)

## 4. Prompt log

My messages, in order, with what each led to. Short prompts are quoted as I typed them.

### Planning and setup

| My prompt | What it led to |
|---|---|
| Starting prompt plus the problem statement | Problem analysis, scope, stack, architecture, roadmap, and a list of assumptions |
| "proceed" | Milestones M0 and M1: project setup, seeded command line, data dictionary |
| "after creating the .gitignore file, do i need to paste the file names in the .gitignore file?" | Explanation of ignore patterns |
| "is it enough if i copy pasted those texts in the gitignore file?" | Checks on file name and location |
| "is it ok if i run it like this: ..." (two runs, same random numbers) | Confirmation that the seeded generator is reproducible |

### Master data, transactions and rules (M2 to M4)

| My prompt | What it led to |
|---|---|
| "Proceed" | M2: IDs, master data, first validator, tests |
| "after running this, the following is the output ... is it ok?" | Checked 38 of 38 validation checks and 6 passing tests |
| "after this step, the following is the output ... is it ok?" | Confirmed identical file hashes across two runs |
| "i did not create any github repository, then how can i able to commit?" | Explained local commits versus GitHub |
| "proceed" | M3: incidents, claims, items and documents |
| "you want me to add this line right after the import statements" | Clarified where the line goes |
| "lemme where i can find those empty files" | How to inspect the documents table |
| "after executing these two commands, the output is ... is it ok?" | Confirmed the document checks |
| "proceed" | M4: the rules engine |
| "is the following output is ok" (preview showing 1 duplicate) | The AI spotted an accidental duplicate in the clean data and gave a fix |
| "is this output is ok" (second preview) | Confirmed 0 duplicates |

### Workflow, anomalies and reporting (M5 to M7)

| My prompt | What it led to |
|---|---|
| "proceed" | M5: workflow, reserves, settlements and the audit log |
| "when i run the python -m pytest -v, i got the following result" (6 failures) | Root cause found (approval authority too low for large payouts) and fixed |
| "after running these commands, i am getting the given result. Is it ok?" | Confirmed 140 of 140 checks and identical event hashes |
| "what should i do now?" (git push had no destination) | Created the GitHub repository and connected it |
| "suggest a git repo name for this problem" | Name options; I chose `Insurance-claims-synthetic-data` |
| "proceed", then "Continue" (the first reply was cut off) | M6: anomaly injection and ground truth |
| "i didn't do this step. gimme steps to finish the M6." | Steps and an updated data dictionary |
| "proceed" | M7: detection scoring and the validation report |
| "is there any issue" (I had typed `python -v` instead of `python -m`) | Explained the difference |
| "is this output ok for M7" | Confirmed 51 tests, 147 of 147 checks, 0 misclassified claims |

### Export, documentation and final checks (M8 and M9)

| My prompt | What it led to |
|---|---|
| "proceed" | M8: CSV, JSON and SQL exports, manifest, reproducibility proof |
| "is the output ok?" | Confirmed 36 of 36 identical files and a control run that differs |
| "what is the use of running this command ..." | Explained the SQL load check |
| "proceed", then "Continue" | M9: README, demo script, manifest checker, interview notes |
| "after running this command, the output is ... is it ok" | Confirmed 57 passing tests |
| Outputs of the generate, verify and demo commands: "is it ok?" | Confirmed checksums and the demo output |
| "what is the issue" (typed `cd clone test` for a folder named `clone-test`) | Explained the typo |
| "when i try to install the requirements, i am not able to install the pytest, numpy, pandas. Why?" | Troubleshooting steps for the fresh-clone install |
| "whare should i execute this, in the clone or original folder" | Clarified which folder |
| "both the original and the clone folders are using python 3.11.9 versions" | Narrowed down the cause |
| "what are the loop holes that are in this project ..." | Review of weaknesses and a handoff prompt |

## 5. Decisions I made

* Approved the "generator-first" interpretation (a seeded data generator with a rules engine) and the assumptions: four products, USD, IDs carry the dataset year 2026, and a definition of "duplicate incident".
* Chose the working environment and tools: Windows, PowerShell, Python 3.11.9, VS Code, GitHub.
* Created the GitHub repository and chose its name.
* Asked for a weakness review before submitting.

## 6. Problems I ran into

| Problem | What happened | Status |
|---|---|---|
| Six workflow tests failed with `ValueError: high <= 0` | I pasted the output; the AI found that some payouts exceeded the top approval authority; the fix was applied | Resolved, tests pass |
| `python -v pytest -v` | A typo; the AI explained `-m` versus `-v` | Resolved |
| `git push` had no destination | I asked what to do; created the repo and set the remote | Resolved |
| I skipped a data dictionary update | I said so and asked for the steps | Done afterwards |
| `cd clone test` | A typo in a folder name | Resolved |
| `pip install` of the requirements failed in a fresh clone | Reported with Python version | **Fill in the current status before submitting** |

## 7. What I can explain

*Tick only what is true for you. Do not tick anything you cannot explain without notes.*

* [ ] Why the project is a generator driven by a rules engine rather than a web app
* [ ] How the seed makes every run identical, and what the control run proves
* [ ] The order of the business rules, and why an incident on the cancellation date is covered but one day later is not
* [ ] How a claim moves from submission to payment and what the audit log records
* [ ] The difference between the two anomaly layers
* [ ] How ground truth is produced and why it cannot leak into the inputs
* [ ] What the detection scores prove and what they do not
* [ ] The two bugs described in section 6 and how the root causes were found

## 8. Checks I ran myself

These are from outputs I pasted into the conversation:

* `python -m pytest`: 57 passed
* `python -m generator`: 147 of 147 checks on the clean data; the failing checks after injection match the injected defects; 0 misclassified claims
* `python scripts/check_reproducibility.py`: 36 of 36 files identical across two runs; a different seed gives different files
* `python scripts/verify_manifest.py data`: all checksums match
* `python scripts/demo.py`: ran and showed the expected claim story and injected cases

## 9. Short statement for the submission form

"I built this project with the help of an AI assistant (Claude). I defined the approach and rules, ran and verified every step on my own machine, reported errors, and made the setup and Git decisions. The AI wrote the code, tests and documentation and diagnosed the errors I reported. My prompts and the AI's replies are in the attached log, and I can explain the design in an interview."
