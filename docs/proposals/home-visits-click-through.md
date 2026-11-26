# Manual click-through: on-demand home visits (phase 7)

Run the backend with `DISABLE_PAID_SERVICES=1`, then `npm run dev` and open http://localhost:3000 (use `localhost`: browser location needs HTTPS or localhost).
You need a patient, a doctor, and the demo doctors if you want matching without setting a doctor up by hand.

## Set up (once)
1. `backend\venv\Scripts\python.exe scripts\home_visit_demo.py seed` creates four `[DEMO]` doctors (F-10, G-11, Blue Area, Bahria Town). To sign in as one, set `$env:DEMO_DOCTOR_PASSWORD` first and use `demo-homevisit-f10@example.test` (or g11, bluearea, bahria).
2. Or use your own doctor: sign in, open **My profile**, scroll to **Visiting patients at home**, tick **I take home visits**, set a radius (for example 10), press **Use my current location** (or **Type latitude and longitude instead**, for example 33.6938 and 73.0129), **Save**. Switching it on without a location says so.

## Patient (open /emergency)
1. The red 1122 notice is at the top. Signed out you are asked to sign in; a doctor account is told to use the dashboard.
2. Answer **Yes** to any safety question: an emergency notice appears and **Send request** is disabled.
3. Answer **No** to all, type "I have chest pain since morning" as the problem, press **Use my current location**, fill phone and address, **Send request**: only the 1122 notice and "Nothing was saved and no doctor was contacted". **Start over** brings the form back.
4. Type "knee joint pain and swelling": "Better seen in a clinic" with a link to book. Nothing is saved.
5. Press **Use my current location** and allow it: "Location found, accurate to about N m" and "Coordinates used: ...". On a computer a result worse than 1 km shows an amber "only approximate" note. Block location in the browser and try again: a plain message and the latitude and longitude boxes appear. Latitude 95 is refused.
6. Send a request without a location: "Add your location first."
7. With a mild reason ("fever and a cold for two days"), a location, a phone and an address, choose **Match me automatically** and **Send request**. The tracker shows "Asking doctor 1 of up to 5" with a countdown. There is no map and no moving pin.
8. Choose **I will choose a doctor** instead: **Find doctors near me** lists doctors with "straight-line distance, about X km" (never a road distance or minutes). **Send request** goes to that doctor only.
9. **Cancel this visit** asks for a confirmation and ends it.

## Doctor (open /dashboard/doctor, card **Home visits**)
1. A waiting request shows the reason, "straight-line distance" and "Answer within m:ss". The patient's name, phone and address are not shown yet. **Decline** hands it to the next doctor (the patient sees "Asking doctor 2").
2. **Accept**: the phone (a tap-to-call link), the typed address and the coordinates appear, marked "Straight-line only, not a route". Your own record access for this patient is still locked (accepting grants nothing).
3. Type an estimate (for example 15) and press **I am on my way**; the patient's tracker says "Doctor's estimate: about 15 minutes ... not a tracked arrival time". An estimate of 500 is refused.
4. **I have arrived**, then **The visit is finished**, then fill **What you found**, **Advice given**, **Follow-up** and **Save summary and close**. The visit moves to **Past home visits** with the summary; the phone and address are gone.
5. **This is an emergency** (at any live step) asks for a confirmation and tells the patient to call 1122.
6. With nothing waiting the card says so and links to **Home-visit settings**.

## Back as the patient
1. The visit shows each step with its time, then the doctor's findings, advice and follow-up under **Earlier requests**. After an emergency referral the 1122 notice is shown.
2. **Notifications** has a **Home visits** filter with one message per step; none contains your reason or address.
3. A request left unanswered for 2 minutes moves to the next doctor; after 5 doctors (or none eligible) it ends as "No doctor found".
4. Check the page at phone width (390 px): nothing scrolls sideways.

## Clean up
`backend\venv\Scripts\python.exe scripts\home_visit_demo.py remove` deletes the demo doctors (patients' visits stay, without a doctor).
