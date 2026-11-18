# Capital One Bug Bounty Program Policy (HackerOne)

- **Organisation:** Capital One
- **Source:** https://hackerone.com/capital-one-bounty/policy_versions
- **Source format:** HackerOne policy API (JSON)
- **Retrieved:** 2026-11-18
- **Published:** 2026-07-21
- **Policy version:** latest of 7 published versions (HackerOne id 3778866)
- **Gold Standard Safe Harbor:** False; **AI Safe Harbor:** None

---
Capital One Bug Bounty Program Terms 
=======================
Capital One looks forward to working with the security community to keep our businesses and customers safe. Please read this program policy in its entirety before you start any testing.

Capital One has established this public bug bounty program to facilitate our exchange of information about potential vulnerabilities, establish rules for vulnerability testing, and provide a safe harbor for individuals who follow these rules. 

Any persons seeking to participate in Capital One’s public bug bounty program must **at all times** adhere to the rules and scope prescribed below in order to remain eligible for a bounty payment by Capital One. Any activity deemed by Capital One, in its sole discretion, to violate these requirements may result in your report being deemed ineligible for a bounty payment, and should that activity violate HackerOne’s Code of Conduct, may also result in your removal from future participation in Capital One’s bug bounty program.


Eligibility
===================
In order to be eligible for a bounty within Capital One’s Bug Bounty Public Program, you must:

- Be at least the age of maturity in the country in which you reside and in which you are performing your activities in furtherance of our program.
- Be acting in your individual capacity and not on behalf of any other company with whom you are now or were at any prior time employed or have otherwise been retained.
- Not now be, nor within the past six months have been, a Capital One employee, contractor, consultant, or a cohabitant with or member of the immediate family of any such person (meaning spouses, siblings, parents, children, grandparents, and grandchildren, whether as “in-laws” or by current or past marriage(s), adoption, or other family extension).
- Not be a resident of a jurisdiction against which the United States has issued comprehensive sanctions or other trade restrictions (e.g., Iran, North Korea, Syria, Cuba, the Crimea region of Ukraine) or be an individual against whom the United States has issued blocking sanctions (e.g., be placed on the Office of Foreign Assets Control (OFAC) Specially Designated Nationals or Blocked Persons List).
- Perform all security testing and related research in accordance with applicable laws.
Be true and accurate in all of the representations that you have made to HackerOne as a Finder, and you must acknowledge that Capital One is relying on such representations.


Disclosure Policy
===================
- Do not discuss any vulnerabilities (even resolved ones) outside of the program without express consent from Capital One.
- Follow HackerOne's [disclosure guidelines](https://www.hackerone.com/disclosure-guidelines). 
- Submit only original vulnerability reports identified by you as a HackerOne user and do not copy or otherwise reproduce works to which you have any reason to believe others may have a claim.


Response Targets
===================
Capital One will make a best effort to meet the following response targets for hackers participating in our program:
- Time to triage - Refer to [HackerOne Triage policy](https://www.hackerone.com/hackerones-depth-approach-vulnerability-triage-and-validation)
- Time to bounty (from triage) - 15 business days

We’ll try and keep you informed about our progress throughout the process.


Program Rules
===================
- Please provide detailed reports with reproducible steps and screenshots. If the report is not detailed enough to reproduce the issue, the issue will not be eligible for a bounty.
- Submit one vulnerability per report, unless you need to chain vulnerabilities to provide impact.
- When duplicates occur, we award only the first report that was received (provided that it can be fully reproduced).
- Multiple vulnerabilities caused by one underlying issue will be awarded one bounty.
- Social engineering (e.g., phishing, vishing, smishing) is prohibited.
- Make a good faith effort to avoid privacy violations, destruction of data, and interruption or degradation of our service. Please review our [privacy policy](https://www.capitalone.com/privacy/online-privacy-policy/) and [terms](https://www.capitalone.com/digital/corporate-terms/) to ensure compliance with our terms of use. 
- **Only interact with accounts you own or with the explicit permission of the account holder.** Capital One takes the privacy and security of our customers seriously, and therefore, it is strictly against our policy to perform actions that will affect other user accounts that are not your own. If you think there may be a vulnerability that you are only able to prove using accounts that are not your own, do not test, and instead bring this to the attention of the Capital One team. Interacting with an account you don’t own or have permission to interact with will disqualify you from a potential bounty.
- Do not put any Capital One data or customers at risk. Please refer to Hacker One’s [Code of Conduct](https://www.hackerone.com/policies/code-of-conduct). Breach of terms of the program may result in removal from Capital One’s Bug Bounty program and disqualification from receiving bounty payments.
- Employ commercially reasonable security measures to protect any systems or devices that you utilize in connection with your testing or research of Capital One systems.
- Please note that zero-day vulnerabilities (vulnerabilities that were not previously known to the security community) are not eligible for awards unless you identify a zero-day vulnerability on an in-scope system more than 30 days after the zero-day vulnerability was disclosed to the security community.


Testing Guidelines
=====================
Please review all guidelines listed below. **Failure to comply with testing guidelines may result in disqualification of potential bounty and removal from the program.**

- Confine scans on a single endpoint to a 500ms delay
- Vulnerabilities reported by automated scanning tools without sufficient additional analysis will be considered Informational.
- It is against our policy to perform actions that will impact other accounts that are not your own. You may only interact with your own accounts for testing. - If you need assistance demonstrating further impact, please contact the H1 triage team.
- Be mindful of using automated form submission tools like Selenium when interacting with forms and input fields. Do not spam or brute force our forms, doing so may result in your activity being considered a DoS attack, which is out of scope and a violation of HackerOne’s [Code of Conduct](https://www.hackerone.com/policies/code-of-conduct).
- Use the latest official releases of the mobile app in the Google Play and Apple app store. POCs using any versions older than the most recent version may not be eligible for bounty.
- Please flag your traffic with the following User-Agent header to identify yourself as a member of the bug bounty program: HackerOne-[hacker handle]-BB

Accessing live customer/associate data containing PII
---------------------------
- If the potential exists to access PII as part of a test, ***stop*** testing and consult the Capital One team. Please email support@hackerone.com.
- If you unintentionally access PII, halt testing and notify the Capital One team ***immediately***. The Capital One team will provide instructions concerning the conduct of any further testing, as well as the steps you will need to take to confirm any PII accessed as part of the test has been fully removed from your system. Again, email support@hackerone.com to reach us.


Scope
=====================
Only assets listed as "In Scope" on the Scope page are valid targets for this program. Reports for assets not listed as "in scope" will not be eligible for bounty in this program, even if they are accepted to be fixed.

If you have discovered a vulnerability on an asset that is not listed as "in scope" for Capital One's bug bounty program, but it is on a Capital One asset, please submit it to Capital One's Vulnerability Disclosure Program here:  https://hackerone.com/capital-one

Out of Scope Vulnerabilities
=======================
When reporting vulnerabilities, please consider (1) attack scenario/exploitability, and (2) the security impact of the bug. The following issues are considered out of scope:
- Vulnerabilities related to COOP security header.
- Clickjacking on pages with no sensitive actions.
- Unauthenticated/logout/login CSRF.
- Attacks requiring MITM or physical access to a user's device.
- Previously known vulnerable libraries without a working Proof of Concept.
- Comma Separated Values (CSV) injection without demonstrating a vulnerability.
- Missing best practices in SSL/TLS configuration.
- Any activity that could lead to the disruption of our service (DoS).
- Web cache poisoning resulting in DoS.  
- Content spoofing and text injection issues without showing an attack vector/without being able to modify HTML/CSS
- Social Engineering. For example, attempts to steal cookies, fake login pages to collect credentials
- Phishing
- HTTP Request Smuggling
- The submission of form data via HTTP sites
- Google Maps API key exposure/misconfiguration(s)
- Zombie Zoom links for expired Capital One meetings
- Leaked credentials in external logs such as Stealer Logs
- Prometheus metrics data without further proof of impact

Open Redirects
---------------------------
Open redirect vulnerabilities are considered in scope for this program and will be categorized as low severity unless further security impact can be demonstrated.

Web Cache Poison 
---------------------------
Cache Poison reports resulting in XSS or other vulnerabilities (not DoS) will be evaluated on a case by case basis.  Any web cache poisoning resulting in DoS is out of scope.  

Third Party Reports
---------------------------
Please also note that Capital One employs third party vendors and some subdomains may be managed by third parties. Security issues found in third-party assets which are not managed by Capital One are considered out of scope, are not eligible for a bounty payment, and should be reported to the affected party directly. When issues reported to the Capital One program originate in a different vendor's service, Capital One reserves the right to forward submissions to the affected party without further discussion. Please be sure to check our publicly published IP ranges and conduct all necessary due diligence to determine ownership of an asset prior to testing.

Domain Hijacking/Broken Link Takeover (not to be confused with subdomain takeovers) 
---------------------------
Domain hijacking will be considered only for assets that would reasonably be considered to be under the control of Capital One. Only domains/assets within the last 5 years will be considered impactful. Valid reports of hijacked domains within broken links will be handled on a case by case basis and are eligible for up to a $50 bounty. 

Some examples of domains that may or may not be of interest are found below:
Potentially of interest:
- `capitalonegolftournament.com`
- `capitalone<>.com`

Not of interest:
- `novabankassociation.com`
- `weliketoparty.com`


Additional Program Terms
=========================
Relationship of the Parties
-----------------------------
Nothing in these Terms will be construed as creating a joint venture, partnership, employment or agency relationship between you and Capital One, and you do not have any authority to create any obligation or make any representation on Capital One’s behalf or any affiliates.

Capital One Information
--------------------------
Capital One remains the exclusive owner of all right, title, and interest in and to any Confidential Information that you obtain in connection with your participation in the Capital One Bug Bounty Public Program, and any derivative works that you create thereform. “Confidential Information” means any information, in any form (1) that you receive or access in connection with any vulnerability report that you produce as part of your activities in furtherance of our program, including the vulnerability report itself, and (2) of or concerning Capital One that is not already in the public domain. 

By participating in our program, you agree to adhere to the following requirements for the handling of Confidential Information:
- Will use any Confidential Information that you obtain only for the purpose of creating and providing a vulnerability report to Capital One.
- Will not disclose the Confidential Information to any third party without Capital One’s prior written consent, and will keep such information highly confidential at all times.
- Will not copy or otherwise retain any Confidential Information other than the vulnerability report, and once you deliver that vulnerability report to Capital One, you will permanently destroy all copies in your possession.

Safe Harbor
---------------------------
Gold Standard Safe Harbor supports the protection of organizations and hackers engaged in Good Faith Security Research. “Good Faith Security Research” is accessing a computer solely for purposes of good-faith testing, investigation, and/or correction of a security flaw or vulnerability, where such activity is carried out in a manner designed to avoid any harm to individuals or the public, and where the information derived from the activity is used primarily to promote the security or safety of the class of devices, machines, or online services to which the accessed computer belongs, or those who use such devices, machines, or online services.

We consider Good Faith Security Research conducted with a good faith effort to comply with our program policy to be authorized activity that is protected from adversarial legal action by us. We waive any relevant restriction in our Terms of Service (“TOS”) and/or Acceptable Use Policies (“AUP”) that conflicts with the standard for Good Faith Security Research outlined here.

This means that for Good Faith Security Research conducted with a good faith effort to comply with our program policy and while this program is active, we:
- Will not bring legal action against you or report you, including for bypassing technological measures we use to protect the applications in scope; and,
- Will take steps to make known that you conducted Good Faith Security Research if someone else brings legal action against you.

You should contact us for clarification before engaging in conduct that you think may be inconsistent with Good Faith Security Research or unaddressed by our policy. Keep in mind that we are not able to authorize security research on third-party infrastructure, and a third party is not bound by this safe harbor statement.

Clarifications on Safe Harbor
-------------------------------
We consider Good Faith Security Research to be authorized activity that is protected from adversarial legal action by us. We waive any relevant restriction in our Terms of Service (“TOS”) and/or Acceptable Use Policies (“AUP”) that conflicts with the standard for Good Faith Security Research outlined here.

This means that, for activity conducted within the scope of our Bug Bounty Program and in accordance with our terms we:
- Will not bring legal action against you or report you for Good Faith Security Research, including for bypassing technological measures we use to protect the applications in scope; and,
- Will take steps to make known that you conducted Good Faith Security Research if someone else brings legal action against you.

Changes to the Rules
------------------------
Capital One reserves the right to change these rules or cancel the Bug Bounty Public Program in its entirety at any time without prior notice. Any changes to the program or these Rules will be posted on this page. If you continue to participate in the program after such changes are posted, you acknowledge your obligation to follow the program rules as modified. It is thus important that you regularly check this page for any changes made to these rules or to the program more generally.
