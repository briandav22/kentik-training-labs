"""The lab site's catalog: what each tile and lab page shows (python3 lab.py ui).

labs.py owns the tickets, the customer's answers, the hints, the faults and the checks. This file adds
what the site needs around them: the tracks, how long a lab takes, what it practices, its steps, what
success looks like, what the portal needs before it starts, what it adds to the portal (so a reset can
take it out again), and the answer for the instructor.

The steps came from the course (kentik-training: public/js/lessons/d1-day-one.js and d2-day-two.js),
where the labs lived until Nov 20, 2026, when Brian moved them out so the course and the labs can change
on their own. The course now pauses at each lab and sends the room here.

Like the tickets, nothing a student reads before asking for a hint may give the fault away: not the
tile, not the steps, not what to look for. tests/test_site.py checks it with the words the ticket test
uses. The instructor's answers are served only by /api/answer, never with the catalog.
"""
from typing import Dict, List, Optional

from . import labs

TRACKS: List[Dict] = [
    {"id": "setup", "title": "Get set up", "sub": "Once, at the start: your host, your agent and your portal."},
    {"id": "flow", "title": "Get flow into Kentik", "sub": "Something in the setup is wrong. Find it and fix it."},
    {"id": "explore", "title": "Ask the data", "sub": "Data Explorer on your own traffic."},
    {"id": "cases", "title": "Cases", "sub": "The setup is fine. The answer is in the traffic."},
    {"id": "platform", "title": "Beyond flow", "sub": "Alerting, NMS, synthetics and Kentik AI."},
]

# Each lab: id (the page's address), track, engine (the lab.py lab it starts, 0 for a healthy network,
# None for none), replay (it starts a lab you've done before, so its pages may name that lab's answer),
# label and title (an engine lab's title comes from labs.py), art (the tile's drawing in ui/art.js),
# time in minutes, level, course (the lesson that sends the room here), line (the tile's one line),
# goal, find (what to find out), steps (text, or {"cmd", "text"}), look, stuck, key (the takeaway),
# needs and adds (the portal before and after: what a reset takes out), answer (instructor only).
LABS: List[Dict] = [
    # ---------------------------------------------------------------- get set up
    {"id": "setup", "track": "setup", "engine": None, "label": "Setup", "title": "Set up your host", "art": "setup",
     "time": 20, "level": "Start here", "course": "get-connected",
     "line": "The Universal Agent on your Linux host, talking to your own portal.",
     "goal": "Get a running, authorized Universal Agent onto your Linux host.",
     "find": ["Does the agent install and start on this host?", "Does your portal see the agent?",
              "Is something listening for flow on UDP 9995?"],
     "steps": [
         "Open your Kentik portal in a browser tab and leave it open.",
         "Copy the **Universal Agent** install command from your portal and run it on this host. On the older "
         "Launchpad hosts the download fails the first time: run the commands in the setup guide, then run the "
         "install again.",
         "Authorize the agent in your portal.",
         {"cmd": "sudo ss -ulnp | grep 9995", "text": "Check that something now listens for flow on UDP 9995."},
     ],
     "look": "Your agent authorized in your portal, and one line from ss showing a program on UDP 9995.",
     "stuck": "Still failing after the guide? Keep the error on screen and ask your instructor.",
     "key": "This is what a customer does on day one: an agent inside their network, calling out to Kentik.",
     "needs": [], "adds": ["agent"],
     "answer": "Nothing to find: a setup. The agent install command carries each student's own account details, "
               "so nobody should paste it into chat or share a screen with it visible. Brian: the install guide "
               "for the older Launchpad hosts isn't in the labs yet."},
    {"id": "portal", "track": "setup", "engine": None, "label": "Setup", "title": "Connect your portal", "art": "portal",
     "time": 5, "level": "Start here", "course": "get-connected", "page": "portal",
     "line": "Your portal's email and API token, so the site can set labs up and clean them away.",
     "goal": "Give the lab site your portal's email and API token.",
     "find": [], "steps": [], "look": "", "stuck": "", "key": "", "needs": [], "adds": [], "answer": ""},

    # ---------------------------------------------------------------- get flow into Kentik
    {"id": "lab-1", "track": "flow", "engine": 1, "label": "Lab 1", "art": "first-flows",
     "time": 20, "level": "Start here", "course": "get-connected",
     "line": "The customer is sending flow. Their portal is empty.",
     "goal": "See the flow arrive, then onboard the three devices so Kentik shows their traffic.",
     "find": ["Which devices are sending, and from which addresses?", "What does Kentik need to know about each one?",
              "How do you prove the flow arrived?"],
     "steps": [
         {"cmd": "sudo python3 lab.py up && sudo python3 lab.py start 1", "text": "Start the made-up network and the lab. "
          "The Launch button does the same."},
         {"cmd": "sudo tcpdump -i lo -n -c 6 udp port 9995", "text": "Check that flow is arriving. Which addresses is it from?"},
         {"cmd": "python3 lab.py agent", "text": "Run the agent's health check. Are your devices registered in Kentik yet?"},
         "Onboard each device in your portal: its name and sending address, through your agent.",
     ],
     "look": "Three devices in your portal, each showing traffic in **Data Explorer**.",
     "stuck": "Need the devices' names? Ask the customer. No flow from one? Its sending IP in Kentik must match the "
              "source address tcpdump shows.",
     "key": "Onboarding is a conversation: you need facts from the customer before you can click anything.",
     "needs": ["agent"], "adds": ["devices"],
     "answer": "Nothing is wrong. Three devices send NetFlow v9 to 127.0.0.1:9995 and none is in Kentik yet. Add "
               "edge-rtr-01 (10.1.0.1), core-sw-01 (10.1.0.2) and branch-rtr-01 (10.2.0.1). Collect who saw flow "
               "first, and what tripped up the rest."},
    {"id": "lab-2", "track": "flow", "engine": 2, "label": "Lab 2", "art": "still-nothing",
     "time": 10, "level": "Easy", "course": "lab-still-nothing",
     "line": "Devices added, export configured, and still no traffic.",
     "goal": "Work out why the agent receives nothing, and fix it.",
     "find": ["Is flow arriving at the host at all?", "Is it arriving where the agent listens?",
              "Who has to change something: the customer, or us?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 2", "text": "Open the ticket. The Launch button does the same."},
         "Ask the customer whatever you like. Notice what they're sure of and what they aren't.",
         {"cmd": "sudo tcpdump -i lo -n -c 6 udp", "text": "Look at the flow yourself. Read the whole line: where "
          "from, and where to."},
         {"cmd": "sudo python3 lab.py check", "text": "Fix it, then check your work. Check my work does the same."},
     ],
     "look": "Check says the devices send to a port where something is listening, and traffic returns in your portal.",
     "stuck": "Take a hint: they get more specific each time.",
     "key": "Don't take anyone's word for it. Look at the packets.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "The devices send to UDP 2055; the agent listens on 9995. Both fixes are right: the customer changes "
               "the export (lab.py tell port 9995), or the agent listens on 2055 too."},
    {"id": "lab-3", "track": "flow", "engine": 3, "label": "Lab 3", "art": "one-missing",
     "time": 10, "level": "Medium", "course": "lab-one-missing",
     "line": "Two devices look fine. The one that matters most shows nothing.",
     "goal": "Work out why one device's flow is ignored, and fix it.",
     "find": ["What is different about this one device?", "Does what the customer told you match what the device does?",
              "Where would you fix it: on the router, or in Kentik?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 3", "text": "Open the ticket."},
         "Ask the customer which address each device sends from.",
         {"cmd": "sudo tcpdump -i lo -n -c 9 udp port 9995", "text": "Now look. List the source addresses you really see."},
         "Compare the two lists.",
         {"cmd": "sudo python3 lab.py check", "text": "Fix it on the router or in Kentik, then check."},
     ],
     "look": "edge-rtr-01 shows traffic in your portal again.",
     "stuck": "Take a hint: they get more specific each time.",
     "key": "The sending address in Kentik must match the address the flow really comes from.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "edge-rtr-01 exports from 10.1.1.1 (GigabitEthernet0/0/4), not its loopback 10.1.0.1. Two right fixes: "
               "the router exports from its loopback (lab.py tell source edge-rtr-01 loopback), or the device's "
               "sending IP changes in Kentik. python3 lab.py agent shows the unmatched address: keep it for the debrief."},
    {"id": "lab-4", "track": "flow", "engine": 4, "label": "Lab 4", "art": "yesterday",
     "time": 12, "level": "Hard", "course": "lab-worked-yesterday",
     "line": "Fine yesterday. This morning, no new flow from anything.",
     "goal": "Flow reaches the host and the agent is up. Find out why they never meet.",
     "find": ["Is flow still arriving at the host?", "Is the agent still listening?",
              "If both are true, what sits between them?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 4", "text": "Open the ticket."},
         {"cmd": "sudo tcpdump -i lo -n -c 6 udp port 9995", "text": "Is flow arriving?"},
         {"cmd": "sudo ss -ulnp | grep 9995", "text": "Is the agent listening?"},
         {"cmd": "sudo python3 lab.py check", "text": "Find what sits between the two, remove it, then check."},
     ],
     "look": "Check says flow is reaching the agent again, and traffic returns in your portal.",
     "stuck": "Both look fine? Ask the customer what changed. Then the hints get more specific.",
     "key": "Arriving is not the same as delivered.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "One iptables rule tagged klab drops UDP 9995 on the host: tcpdump sees every packet, the agent gets "
               "none, and the rule's counter climbs. Find it with sudo iptables -L INPUT -n -v --line-numbers and "
               "delete it. Putting the network back to healthy also clears it."},
    {"id": "lab-5", "track": "flow", "engine": 5, "label": "Lab 5", "art": "numbers",
     "time": 10, "level": "Medium", "course": "lab-numbers-wrong",
     "line": "Two devices see the same users. Kentik says one carries far less.",
     "goal": "Explain why one device reads low, and make Kentik show the truth.",
     "find": ["How far apart are the two numbers?", "Is the gap a round figure?", "What would Kentik need to know to fix it?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 5", "text": "Open the ticket. Give it five minutes to collect."},
         "In **Data Explorer**, compare the traffic of `core-sw-01` and `edge-rtr-01` over the last 15 minutes. "
         "How many times smaller is the switch?",
         "Ask the customer the question that number suggests.",
         "Fix it in your portal, on `core-sw-01`.",
         "Wait a few minutes and compare the two devices again.",
     ],
     "look": "For new traffic, core-sw-01 and edge-rtr-01 show about the same volume for HQ users.",
     "stuck": "Work out the gap first: a round number is a clue. Then the hints get more specific.",
     "key": "A device that doesn't say everything about its flow makes every number wrong by the same factor.",
     "needs": ["agent", "devices"], "adds": ["device-setting"],
     "answer": "core-sw-01 samples 1 in 100 and doesn't say so. Set the device's sample rate to 100 in Kentik; it "
               "applies to new flow. Start this lab a few minutes early so the gap is steady."},

    # ---------------------------------------------------------------- ask the data
    {"id": "questions", "track": "explore", "engine": 0, "label": "Explore", "title": "Twelve questions", "art": "questions",
     "time": 25, "level": "Easy", "course": "twelve-questions",
     "line": "The questions every SE gets asked, answered from your own data.",
     "goal": "Use Data Explorer on your own data. Name the group by, measure and filter each time.",
     "find": ["Who are the top talkers, and which application moves the most?", "What leaves for the internet?",
              "How much does the branch send to the HQ servers?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 0", "text": "Put the network back to healthy. The Launch button does the same."},
         "In **Data Explorer**: who are the top talkers? Which application moves the most bytes?",
         "Which destination has the most flows but almost no bytes? Why would that be?",
         "Filter to one device, `edge-rtr-01`. What leaves for the internet, and through which interface?",
         "How much traffic does the branch (`10.2.20.0/24`) send to the HQ servers (`10.1.60.0/24`)?",
         "Switch to all devices. Why did the total for HQ users roughly double?",
     ],
     "look": "A different table for each question, built by changing only the dimensions, the metric and the filters.",
     "stuck": "Start every question from the same query and change one thing at a time.",
     "key": "Group by, measure, filter. Twelve questions, three moves.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "Top internet destination by bytes: software updates (192.0.2.80) or the shop (203.0.113.10). Top "
               "internal server: app-01 (10.1.60.25). DNS (UDP 53 to 198.51.100.53) has the most flows and the fewest "
               "bytes. edge-rtr-01 and core-sw-01 send the most flow. The HQ total doubles across all devices because "
               "each conversation is seen by two of them. Run it as a race in pairs."},

    # ---------------------------------------------------------------- cases
    {"id": "case-1", "track": "cases", "engine": 6, "label": "Case 1", "art": "crawling",
     "time": 20, "level": "Medium", "course": "case-crawling",
     "line": "Phones are ringing. The ISP says it isn't them.",
     "goal": "Find what the traffic is, who is behind it, and what you'd tell the service desk.",
     "find": ["What is filling the internet link?", "Is it one person, one site or everyone?",
              "What should change, and how will you know it worked?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 6", "text": "Start the case. Give it five minutes."},
         "In **Data Explorer**, look at `edge-rtr-01` over the last 30 minutes. When did the total jump?",
         "Group by destination address, then by destination port. What is everyone talking to?",
         "Count the inside addresses involved. One laptop, one site, or everyone?",
         "Write one sentence for the service desk: what it is, who, and what to change.",
     ],
     "look": "One destination taking most of the link, from many inside addresses at the same moment.",
     "stuck": "Stay on one device, edge-rtr-01, so you count each conversation once.",
     "key": "Group by turns \"how much\" into \"what\".",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "Software updates from 192.0.2.80, pulled by nearly every user at both sites at once, for 30 minutes. "
               "Spread or cache the updates."},
    {"id": "case-2", "track": "cases", "engine": 7, "label": "Case 2", "art": "dns-alert",
     "time": 20, "level": "Medium", "course": "case-dns",
     "line": "One laptop, one lookup, one alert. That's all security has.",
     "goal": "Rebuild what one laptop did, before and after the alert.",
     "find": ["When did the laptop first talk to that address?", "How much data went out, and when?",
              "What did it touch inside before that?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 7", "text": "Start the case."},
         "In **Data Explorer**, filter to source address `10.1.20.77` and widen the time range to the whole day.",
         "Group by destination address. Which destination is not one the other laptops use?",
         "Look at that one destination over time. When did it start? What changed in the last few minutes?",
         "What did the laptop talk to inside the network just before the big transfer?",
     ],
     "look": "Hours of small, regular check-ins to one outside address, then a large transfer out, with an inside "
             "conversation just before it.",
     "stuck": "Filter on the destination 203.0.113.66 and group by source address to see who else talks to it.",
     "key": "DNS says what a host asked for. Flow says what it did next.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "Small regular check-ins to 203.0.113.66 on port 443 since the lab network started; connections to "
               "db-01 (10.1.60.40, port 5432) for three minutes, then a large upload to 203.0.113.66 for fifteen. The "
               "trail is hours older than the alert; data left; look at the database."},
    {"id": "case-3", "track": "cases", "engine": 8, "label": "Case 3", "art": "attack",
     "time": 15, "level": "Medium", "course": "case-attack",
     "line": "The link is full, the web server stopped answering, and none of it looks like customers.",
     "goal": "Describe the attack in one sentence: what, from where, at what.",
     "find": ["What is arriving, and from how many sources?", "What marks it out from normal traffic?",
              "What alert would have told you in the first minute?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 8", "text": "Start the case. Give it five minutes."},
         "In **Data Explorer**, look at traffic arriving on `edge-rtr-01` from the internet. What is the top destination?",
         "Filter to that destination. Group by protocol and by source port. What stands out?",
         "Count the source addresses. Ten? Hundreds?",
         "Write the one sentence a provider or a mitigation tool would need.",
     ],
     "look": "One inside address receiving one kind of packet from many outside addresses.",
     "stuck": "Compare with the same view from an hour ago. What is there now that wasn't there then?",
     "key": "An attack looks like nothing else: many sources, one target, one kind of packet.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "A UDP flood from source port 53 (a DNS reflection pattern) from hundreds of outside addresses to web-01 "
               "(10.1.60.10), arriving through edge-rtr-01, for 30 minutes. Then build the alert that catches it."},
    {"id": "overnight", "track": "cases", "engine": 9, "label": "Overnight", "art": "overnight",
     "time": 10, "level": "Easy", "course": "overnight", "arm": True,
     "line": "Arm it in the evening. In the morning, a ticket about the night.",
     "goal": "Say who touched the servers, what they did and when.",
     "find": ["Which address was behind it, and where is it?", "What exactly did it do?", "When did it start and stop?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 9", "text": "In the evening: arm tonight's event, and leave the lab network "
          "running. Arm for tonight does the same."},
         "In the morning, in **Data Explorer**, set the time range to cover last night.",
         "Filter to destination `10.1.60.0/24`. Group by source address and count the destination ports each one used.",
         "One source stands out from all the others. Which, and where does that address live?",
         "Look at its flows: how many packets each? What does that tell you?",
         "Find the first and last minute it was active.",
     ],
     "look": "One address doing something to the HQ servers that nothing else does, for under an hour.",
     "stuck": "Group by destination port for the whole server subnet. A healthy server uses a handful of ports.",
     "key": "Flow is a record of last night as well as right now.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "10.2.20.44, a branch address, tried hundreds of ports on the HQ servers (10.1.60.0/24) with single-packet "
               "connection attempts for about forty minutes, about six hours after the lab was armed. Start in five "
               "minutes runs it now, for a dry run."},
    {"id": "cold-case", "track": "cases", "engine": 10, "label": "Cold case", "title": "The cold case", "art": "cold-case",
     "time": 30, "level": "Hard", "course": "cold-case",
     "line": "Two days of your own data. Show the CIO something they didn't know.",
     "goal": "Find what is leaving the network that shouldn't be, and say it in two sentences.",
     "find": ["What is leaving the network that doesn't belong?", "Which system is behind it, and since when?",
              "How would you explain it to the CIO in two sentences?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 10", "text": "Start the case. Give it ten minutes while you plan."},
         "Decide your three moves before you click: what to group by, what to measure, what to filter.",
         "Find it in your own portal. Use anything from the last two days, including AI Advisor.",
         "Work out which system it is, where the traffic goes, and when it started.",
         "Write your two sentences for the CIO.",
     ],
     "look": "One system that has no business talking to the internet, sending a steady stream to one outside address.",
     "stuck": "Start from traffic leaving through edge-rtr-01 to the internet and group by source address. Who is on "
              "that list that wasn't yesterday?",
     "key": "The best demo is the customer's own surprise.",
     "needs": ["agent", "devices"], "adds": [],
     "answer": "db-01 (10.1.60.40), a database server, is sending a large steady stream to 198.51.100.200 on port 22, "
               "starting when the case began. Servers that only ever answered inside the network don't open "
               "connections to the internet. About 50 minutes: 30 to investigate, 10 for two presentations, 10 to "
               "debrief."},

    # ---------------------------------------------------------------- beyond flow
    {"id": "alerting", "track": "platform", "engine": 8, "replay": True, "label": "Alerting",
     "title": "Build your first alert", "art": "alerting",
     "time": 15, "level": "Medium", "course": "alerting-basics",
     "line": "Turn the query that found Case 3 into an alert that would have caught it.",
     "goal": "Turn the query that found the attack into an alert policy.",
     "find": ["What is normal for this server?", "Where should the line go?", "Does the alert clear when the attack stops?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 8", "text": "Make sure Case 3's traffic is running. Launch does the same."},
         "In your portal, open the alerting section and start a new alert policy for traffic.",
         "Give it the query from Case 3: traffic to destination `10.1.60.10`, measured in bits per second.",
         "Set a threshold well above the server's normal traffic and well below the attack.",
         "Make it fire after a few minutes above the line, save it, and watch for the alert.",
         {"cmd": "sudo python3 lab.py start 0", "text": "When your alert has fired, stop the attack. Does the alert clear?"},
     ],
     "look": "An active alert naming web-01, which clears a few minutes after the attack stops.",
     "stuck": "Check the server's normal and attack traffic in **Data Explorer** first, and put your line between them.",
     "key": "You found it by looking. An alert finds it for you, in the first minute.",
     "needs": ["agent", "devices"], "adds": ["alert-policy"],
     "answer": "The attack is still running, so a well-built policy fires while they watch. Kentik SE team: confirm "
               "students' portals include alerting."},
    {"id": "nms", "track": "platform", "engine": 11, "label": "NMS", "art": "nms",
     "time": 30, "level": "Medium", "course": "lab-nms",
     "line": "The customer turned SNMP on and added the host. No metrics appear.",
     "goal": "Prove SNMP works from the agent's host, then see the host's health in your portal.",
     "find": ["Does the host answer SNMP at all?", "Does it answer with the details the customer gave you?",
              "What does Kentik show once it works?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 11", "text": "Open the ticket. The lab turns on SNMP on this host."},
         "Ask the customer for the SNMP details.",
         {"cmd": "python3 lab.py snmp test <community>", "text": "Test what they gave you, from the agent's host. No "
          "answer? Ask what changed."},
         "In your portal, add this host to NMS: address `127.0.0.1`, SNMP version 2c, the community string that "
         "worked, polled by your Universal Agent.",
         "Wait for the first poll, then open the device in NMS. Find its CPU, memory and interfaces.",
     ],
     "look": "The host as a device in NMS with real CPU, memory and interface graphs.",
     "stuck": "No answer to the test at all? Launch the lab again and read what it says about snmpd.",
     "key": "Test the credentials yourself from the agent's host before you blame Kentik.",
     "needs": ["agent"], "adds": ["nms-device"],
     "answer": "The customer first gives an out-of-date community string (netops-ro); the right one (kentik-ro) comes "
               "out when asked what changed. Needs the snmpd package on the host."},
    {"id": "synthetics", "track": "platform", "engine": None, "label": "Synthetics",
     "title": "A ping test and a DNS test", "art": "synthetics",
     "time": 30, "level": "Easy", "course": "synth-lab",
     "line": "Two tests from your own agent: what does the path feel like?",
     "goal": "Run two tests from your own host and read what they measure.",
     "find": ["What do latency, loss and jitter look like on a healthy path?", "Which hops does the path cross?",
              "What would you alert on?"],
     "steps": [
         "In your portal, open your Universal Agent and turn on its capability for running synthetic tests.",
         "In the synthetics section, create a network test (ping and traceroute) to `example.com` from your private agent.",
         "Create a DNS test that looks up `example.com`, also from your private agent.",
         "Wait for a few results. On the network test, read latency, loss and jitter, then follow the path hop by hop.",
         "On the DNS test, read the answer and how long it took. What would you alert on?",
     ],
     "look": "Two tests with results from your own agent: a path with hops on one, a resolved address and a time on the other.",
     "stuck": "No results yet? Check the agent shows the test capability as running, and give the test two full intervals.",
     "key": "Flow says what happened. A test says what it felt like.",
     "needs": ["agent"], "adds": ["tests"],
     "answer": "example.com is a reserved example domain that resolves and answers on the real internet, so it is safe "
               "to test. Kentik SE team: confirm the portal steps and labels in the students' portals."},
    {"id": "ai", "track": "platform", "engine": 6, "replay": True, "label": "Kentik AI",
     "title": "Re-solve Case 1 with AI Advisor", "art": "ai",
     "time": 40, "level": "Medium", "course": "ai-lab",
     "line": "Ask AI Advisor the question you answered by hand, and check its work.",
     "goal": "Ask, check the work, teach it your network, and keep the result as a runbook.",
     "find": ["Does its answer match yours?", "What did it miss?", "What changes when it knows your network?"],
     "steps": [
         {"cmd": "sudo python3 lab.py start 6", "text": "Start Case 1's traffic again and give it five minutes."},
         "Ask AI Advisor: \"The internet link on edge-rtr-01 is full. What is using it, who is behind it, and since when?\"",
         "Read its plan and its queries. Does the answer match what you found yesterday? What did it miss?",
         "Add to the custom network context: `10.1.20.0/24` is HQ users, `10.2.20.0/24` is branch users, "
         "`10.1.60.0/24` is HQ servers. Ask again.",
         "Turn the session into a runbook called \"Full internet link\". Read the steps it wrote.",
         {"cmd": "sudo python3 lab.py start 0", "text": "Put the network back to healthy."},
     ],
     "look": "An answer that matches what you found in Case 1, names the user networks, and a saved runbook you could "
             "hand to a colleague.",
     "stuck": "If the answer is vague, give it the device name and a time range in the question.",
     "key": "Check the work: the plan and the queries are the evidence.",
     "needs": ["agent", "devices"], "adds": ["network-context", "runbook"],
     "answer": "Start Case 1's traffic again first so there is something current to find. Kentik SE team: confirm the "
               "portal steps and labels in the students' portals."},
]

# What each kind of thing a lab adds is called on the site, and whether a reset can take it out.
ADDS = {
    "agent": "your Universal Agent",
    "devices": "the lab's three devices",          # not their names: lab 1 gets those from the customer
    "device-setting": "the change you made to core-sw-01",   # not what it is: that would give lab 5 away
    "alert-policy": "the alert policy you built",
    "nms-device": "this host as a device in NMS",
    "tests": "the ping and DNS tests to example.com",
    "network-context": "the custom network context you added",
    "runbook": "the runbook \"Full internet link\"",
}


def by_id(lab_id: str) -> Optional[Dict]:
    return next((lab for lab in LABS if lab["id"] == lab_id), None)


def for_engine(n: int) -> Optional[Dict]:
    """The lab whose own page belongs to engine lab n (not a replay)."""
    return next((lab for lab in LABS if lab["engine"] == n and not lab.get("replay")), None)


def public(lab: Dict) -> Dict:
    """What the site may show anyone: the lab without its answer, plus the ticket and hint count from labs.py."""
    out = {k: v for k, v in lab.items() if k != "answer"}
    n = lab["engine"]
    if n and not lab.get("replay"):                  # a replay reuses a case's traffic, not its ticket
        eng = labs.LABS[n]
        out.setdefault("title", eng["title"])
        out["ticket"] = {"from": labs.CUSTOMER, "lines": eng["ticket"]}
        out["hints"] = len(eng["hints"])
        out["asks"] = sorted(set(labs.QUESTIONS))
    else:
        out["hints"] = 0
    out["adds_text"] = [ADDS[a] for a in lab["adds"]]
    return out


def catalog() -> Dict:
    return {"tracks": TRACKS, "labs": [public(lab) for lab in LABS], "questions": labs.QUESTIONS,
            "customer": labs.CUSTOMER, "adds": ADDS}
