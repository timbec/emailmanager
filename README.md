This is a basic email classifier. It will use a pretrained model from HuggingFace  or some other AI API to classify emails. An early version was built on FastAPI, but since transferred over to Django.

The problem: Probably like most people, I have tens of thousands of unread emails clogging up my inbox. I could manually delete all these emails, but since most are either years old or irrelevant, it would take forever. I want to build a tool that will automatically delete emails that I either no longer need or are irrelevant. 

For now, this is just for personal use but if other people find it useful, and I can work out some security issues, I will convert it into some kind of SaaS. 