# Manual click-through: body weight and height (phase 6)

Run with `DISABLE_PAID_SERVICES=1` for the backend, then `npm run dev` and open http://localhost:3000.
Use two browsers (or one normal and one private window): one patient, one doctor with an active access code grant.

## Patient
1. Sign in as a patient. On the dashboard open **Weight and height**. All three tiles say "Not recorded" and the history says "No weight or height recorded yet."
2. Press **Save reading** with both boxes empty: "Enter a weight, a height, or both."
3. Enter weight 72.5 (kg), height 170, today's date, save. Tiles show 72.5 kg, 170 cm, BMI 25.1, "entered by you". There is no category word, only the reminder that the BMI is not a diagnosis.
4. Enter weight 1 and save: a message from the server says the weight is out of range. Enter 160 with unit **lb**, clear the height, save: the latest weight is 72.57 kg.
5. **Correct** the newest reading to 73: the tile updates. **Remove** a reading: a confirmation appears; Cancel keeps it, Remove deletes it.
6. Open **My profile**: "Latest weight" and "Latest height" show the same values with dates.
7. Pregnancy status: set **Not pregnant**, save, see "set on <today> by you". Set it back to **Not recorded**. (A patient recorded as male cannot choose Pregnant.)
8. Check the page at phone width (390 px): nothing scrolls sideways.

## Doctor (with an active grant for that patient)
1. Open the patient file. **Weight and height: <patient>** shows the patient's readings, the BMI category and the Asian-population note (23.0 / 27.5), and no Correct or Remove button on the patient's own readings.
2. Add a weight for the patient. It shows "entered by Dr ..." and only that reading has Correct and Remove.
3. Add two weights some days apart with a change of 5 % or more within 30 days (the date box accepts past dates): a "significant weight loss/gain, for physician review" notice appears.
4. In **Clinical summary** press Regenerate: a **Body measurements** section lists the values with dates and who entered them; flags appear under Flags; "Weight not recorded" appears under Missing data for a patient with none.
5. In **Prescribe** add Paracetamol 1200 mg, once a day, for an adult with no weight: a red alert for the single-dose maximum and a "weight needed for dose check" notice. With 500 mg only the notice appears.
6. Open "What the check used from this patient's record": weight with its date, pregnancy status, and the Cockcroft-Gault panel ("Information only"), naming any missing input.
7. Back as the patient: the doctor's reading shows "Added by your doctor" with no Correct or Remove, and **Who has seen my record** lists the change.
