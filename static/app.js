const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let me = null, subjects = [], students = [], marks = {};
const today = new Date().toISOString().slice(0,10);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(url, options={}) {
  const res = await fetch(url,{headers:{"Content-Type":"application/json"},...options});
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}
function toast(msg){const t=$("#toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2800)}
function initials(s){return (s||"U").split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase()}
function showView(name){
  ["dashboard","attendance","records","manage"].forEach(v=>$("#"+v+"View").classList.toggle("hidden",v!==name));
  $$(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.view===name));
  $("#crumbName").textContent=({dashboard:"Dashboard",attendance:"Mark Attendance",records:"Attendance Records",manage:"Manage College"})[name]||name;
  const titles={dashboard:["Good to see you, "+me.full_name.split(" ")[0]+" 👋","Here is your attendance workspace at a glance."],attendance:["Mark attendance","Choose your class, subject, and date to record attendance."],records:["Attendance records","Review attendance and export reports for your records."],manage:["College management","Manage demo students, faculty accounts, and subjects."]};
  $("#pageTitle").textContent=titles[name][0];$("#pageSubtitle").textContent=titles[name][1];
  $("#dashboardView").classList.toggle("hidden",name!=="dashboard");
  if(name==="attendance") loadAttendance();
  if(name==="records") renderRecords();
  if(name==="manage") renderManage();
}
function setRoleUI(){
  $$(".faculty-only").forEach(x=>x.classList.toggle("hidden",!["faculty","admin"].includes(me.role)));
  $$(".admin-only").forEach(x=>x.classList.toggle("hidden",me.role!=="admin"));
  $("#userName").textContent=me.full_name;$("#userRole").textContent=me.role;$("#avatar").textContent=initials(me.full_name);
  $("#loginView").classList.add("hidden");$("#contentView").classList.remove("hidden");$("#logoutBtn").classList.remove("hidden");
}
async function boot(){
  try{const d=await api("/api/me");if(d.user){me=d.user;setRoleUI();await loadDashboard();}}
  catch(e){}
}
$("#loginForm").addEventListener("submit",async e=>{
  e.preventDefault();$("#loginError").textContent="";
  try{const d=await api("/api/login",{method:"POST",body:JSON.stringify({username:$("#username").value,password:$("#password").value})});me=d.user;setRoleUI();await loadDashboard();toast("Welcome to your campus workspace!")}
  catch(err){$("#loginError").textContent=err.message}
});
$("#showPassword").onclick=()=>{const p=$("#password");p.type=p.type==="password"?"text":"password";$("#showPassword").textContent=p.type==="password"?"Show":"Hide"};
$("#logoutBtn").onclick=async()=>{await api("/api/logout",{method:"POST"});location.reload()};
$("#menuBtn").onclick=()=>$("#sidebar").classList.toggle("open");
$$(".nav-item").forEach(b=>b.onclick=()=>{showView(b.dataset.view);$("#sidebar").classList.remove("open")});
async function loadDashboard(){
  const d=await api("/api/dashboard");
  if(me.role==="student"){
    $("#dashboardView").innerHTML=`
      <div class="grid stats">
        ${stat("Attendance percentage",d.percentage+"%","◔","Your overall attendance")}
        ${stat("Classes attended",d.present,"✓","Recorded as present")}
        ${stat("Classes missed",d.absent,"×","Recorded as absent")}
        ${stat("Total classes",d.total,"▤","Attendance entries recorded")}
      </div>
      <div class="panel"><div class="panel-head"><div><h3>Recent attendance</h3><p>Your latest subject-wise records</p></div></div>${recordTable(d.records)}</div>`;
  } else if(me.role==="faculty"){
    subjects=d.subjects;
    $("#dashboardView").innerHTML=`
      <div class="grid stats">
        ${stat("Assigned subjects",subjects.length,"▤","Your teaching assignments")}
        ${stat("Attendance entries",d.marked_records,"✓","Records saved by you")}
        ${stat("Academic branches",new Set(subjects.map(s=>s.branch)).size,"⌂","Across your assignments")}
        ${stat("Workspace","Active","↗","Ready for attendance")}
      </div>
      <div class="grid two-col"><div class="panel"><div class="panel-head"><div><h3>Your assigned subjects</h3><p>Select a subject to start marking attendance.</p></div></div>${subjectCards(subjects)}</div>
      <div class="quick-card"><div class="quick-symbol">✦</div><h3>Attendance, without the paperwork.</h3><p>Mark a class, update records, and export attendance reports from one simple workspace.</p><button onclick="showView('attendance')">Mark attendance →</button></div></div>`;
  } else {
    $("#dashboardView").innerHTML=`
      <div class="grid stats">
        ${stat("Students",d.students,"♙","Registered demo student accounts")}
        ${stat("Faculty",d.faculty,"♧","Faculty portal accounts")}
        ${stat("Subjects",d.subjects,"▤","Configured teaching subjects")}
        ${stat("Class sessions",d.sessions,"✓","Dates with recorded attendance")}
      </div>
      <div class="grid two-col"><div class="panel"><div class="panel-head"><div><h3>College workspace</h3><p>Manage the academic data used by attendance.</p></div></div>
      <div class="actions"><span class="muted">Students, faculty, subjects</span><button class="primary" onclick="showView('manage')">Manage records →</button></div></div>
      <div class="quick-card"><div class="quick-symbol">✦</div><h3>A clearer view of attendance.</h3><p>Use the admin workspace to add demo records, configure classes, and review attendance reports.</p><button onclick="showView('records')">View records →</button></div></div>`;
  }
}
function stat(label,value,icon,foot){return `<div class="stat-card"><div class="stat-top">${esc(label)}<div class="stat-icon">${icon}</div></div><div class="stat-value">${esc(value)}</div><div class="stat-foot">${esc(foot)}</div></div>`}
function subjectCards(list){if(!list.length)return `<p class="muted">No subjects assigned yet. Ask the administrator to assign a subject.</p>`;return list.map(s=>`<div class="subject-row" style="display:flex;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--line)"><div class="stat-icon">▤</div><div style="flex:1"><strong>${esc(s.name)}</strong><div class="muted" style="font-size:10px;margin-top:5px">${esc(s.code)} · ${esc(s.branch)} · ${esc(s.year)} · Sec ${esc(s.section)}</div></div><button class="text-link" onclick="showView('attendance');setTimeout(()=>{if($('#subjectSelect')){$('#subjectSelect').value='${s.id}';loadAttendance()}},100)">Open →</button></div>`).join("")}
function recordTable(rows){if(!rows||!rows.length)return `<div class="muted" style="padding:18px 0">No attendance records yet.</div>`;return `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Subject</th><th>Status</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.attendance_date)}</td><td><strong>${esc(r.code||"")}</strong><div class="muted">${esc(r.name||"")}</div></td><td><span class="badge ${r.status==="Present"?"present":"absent"}">${esc(r.status)}</span></td></tr>`).join("")}</tbody></table></div>`}
async function ensureSubjects(){if(!subjects.length){const d=await api("/api/subjects");subjects=d.subjects}}
async function loadAttendance(){
  if(!["faculty","admin"].includes(me.role))return;
  try{await ensureSubjects()}catch(e){toast(e.message);return}
  const host=$("#attendanceView");if(!host)return;
  if(!host.dataset.built){
    host.dataset.built="1";
    host.innerHTML=`<div class="panel"><div class="toolbar"><div class="field"><label>SUBJECT</label><select id="subjectSelect"><option value="">Select subject</option>${subjects.map(s=>`<option value="${s.id}">${esc(s.code)} · ${esc(s.name)} — ${esc(s.branch)} ${esc(s.year)} Sec ${esc(s.section)}</option>`).join("")}</select></div><div class="field"><label>ATTENDANCE DATE</label><input id="attendanceDate" type="date" value="${today}"></div><button class="primary" id="loadClassBtn">Load class →</button></div><div id="classStatus" class="muted" style="font-size:11px;margin:4px 0 15px">Choose a subject and date, then load the student list.</div><div id="studentList"></div><div class="actions"><span id="attendanceSummary" class="muted">No class loaded</span><div><button class="secondary" id="allPresent">Mark all present</button> <button class="primary" id="saveAttendance">Save attendance ✓</button></div></div></div>`;
    $("#loadClassBtn").onclick=loadClass;
    $("#allPresent").onclick=()=>{students.forEach(s=>marks[s.id]="Present");renderStudents()};
    $("#saveAttendance").onclick=saveAttendance;
    $("#subjectSelect").onchange=()=>{students=[];marks={};$("#studentList").innerHTML="";$("#classStatus").textContent="Press Load class to retrieve students."};
    $("#attendanceDate").onchange=()=>{students=[];marks={};$("#studentList").innerHTML=""};
  }else{
    $("#subjectSelect").innerHTML=`<option value="">Select subject</option>${subjects.map(s=>`<option value="${s.id}">${esc(s.code)} · ${esc(s.name)} — ${esc(s.branch)} ${esc(s.year)} Sec ${esc(s.section)}</option>`).join("")}`;
  }
}
async function loadClass(){
  const sid=$("#subjectSelect").value, day=$("#attendanceDate").value;
  if(!sid||!day){toast("Choose a subject and date first.");return}
  try{const d=await api(`/api/attendance?subject_id=${sid}&date=${day}`);students=d.students;marks={};students.forEach(s=>marks[s.id]=s.status||"Present");renderStudents();$("#classStatus").textContent=`${students.length} students · ${day} · Existing saved marks are preloaded.`}
  catch(e){toast(e.message)}
}
function renderStudents(){
  const present=students.filter(s=>marks[s.id]==="Present").length, absent=students.filter(s=>marks[s.id]==="Absent").length;
  $("#attendanceSummary").textContent=`${present} present · ${absent} absent · ${students.length} students`;
  if(!students.length){$("#studentList").innerHTML='<p class="muted">No students are registered for this class.</p>';return}
  $("#studentList").innerHTML=`<div class="table-wrap"><table><thead><tr><th>Student</th><th>Roll number</th><th>Attendance status</th></tr></thead><tbody>${students.map(s=>`<tr><td><div class="student-cell"><div class="mini-avatar">${initials(s.full_name)}</div><div><strong>${esc(s.full_name)}</strong><small>${esc(s.branch)} · ${esc(s.year)} · Sec ${esc(s.section)}</small></div></div></td><td class="roll">${esc(s.roll_no)}</td><td><button class="mark-btn ${marks[s.id]==="Present"?"selected-present":""}" onclick="setMark(${s.id},'Present')">✓ Present</button> <button class="mark-btn ${marks[s.id]==="Absent"?"selected-absent":""}" onclick="setMark(${s.id},'Absent')">× Absent</button></td></tr>`).join("")}</tbody></table></div>`;
}
window.setMark=(id,status)=>{marks[id]=status;renderStudents()};
async function saveAttendance(){
  if(!students.length){toast("Load a class before saving.");return}
  if(students.some(s=>!marks[s.id])){toast("Mark every student first.");return}
  try{const d=await api("/api/attendance",{method:"POST",body:JSON.stringify({subject_id:Number($("#subjectSelect").value),date:$("#attendanceDate").value,marks:students.map(s=>({student_id:s.id,status:marks[s.id]}))})});toast(`Attendance saved for ${d.saved} students.`)}
  catch(e){toast(e.message)}
}
async function renderRecords(){
  const host=$("#recordsView");
  if(me.role==="student"){
    const d=await api("/api/dashboard");
    host.innerHTML=`<div class="grid stats">${stat("Attendance",d.percentage+"%","◔","Overall percentage")}${stat("Present",d.present,"✓","Classes attended")}${stat("Absent",d.absent,"×","Classes missed")}${stat("Recorded",d.total,"▤","Total entries")}</div><div class="panel"><div class="panel-head"><div><h3>My attendance history</h3><p>Subject-wise attendance records.</p></div></div>${recordTable(d.records)}</div>`;
    return;
  }
  try{await ensureSubjects()}catch(e){}
  host.innerHTML=`<div class="panel"><div class="toolbar"><div class="field"><label>SUBJECT FILTER</label><select id="reportSubject"><option value="">All accessible subjects</option>${subjects.map(s=>`<option value="${s.id}">${esc(s.code)} · ${esc(s.name)}</option>`).join("")}</select></div><div class="field"><label>FROM DATE</label><input id="reportStart" type="date" value="${today.slice(0,4)}-01-01"></div><div class="field"><label>TO DATE</label><input id="reportEnd" type="date" value="${today}"></div><button class="primary" id="exportBtn">Export CSV ↓</button></div><p class="muted">Export includes student, subject, date, and status for the selected date range.</p><div class="actions"><span class="muted">Reports are generated from saved attendance records.</span><button class="secondary" id="downloadBtn">Download report</button></div></div>`;
  const exportFn=()=>{const p=new URLSearchParams();if($("#reportSubject").value)p.set("subject_id",$("#reportSubject").value);p.set("start",$("#reportStart").value||"2000-01-01");p.set("end",$("#reportEnd").value||"2099-12-31");window.location="/api/reports.csv?"+p.toString()};
  $("#exportBtn").onclick=exportFn;$("#downloadBtn").onclick=exportFn;
}
async function renderManage(){
  if(me.role!=="admin")return;
  const host=$("#manageView");
  let d={students:[],faculty:[]};try{d=await api("/api/admin/users");subjects= (await api("/api/subjects")).subjects}catch(e){}
  host.innerHTML=`
    <div class="panel"><div class="panel-head"><div><h3>Add student</h3><p>Create a student login account. Username will be the roll number.</p></div></div>
      <form id="studentForm" class="form-grid">
        <label>Roll number<input name="roll_no" placeholder="26XW5A0509" required></label>
        <label>Full name<input name="full_name" placeholder="Student full name" required></label>
        <label>Branch<select name="branch">${["CSE","CSE (AI & ML)","ECE","Civil","Mechanical"].map(x=>`<option>${x}</option>`).join("")}</select></label>
        <label>Year<select name="year">${["1st Year","2nd Year","3rd Year","4th Year"].map(x=>`<option>${x}</option>`).join("")}</select></label>
        <label>Section<input name="section" value="A" required></label><label>Initial password<input name="password" value="Student@123" required></label>
        <button class="primary" type="submit">Add student +</button>
      </form>
    </div>
    <div class="panel section-gap"><div class="panel-head"><div><h3>Add faculty account</h3><p>Create a login for a faculty member.</p></div></div>
      <form id="facultyForm" class="form-grid"><label>Username<input name="username" placeholder="faculty2" required></label><label>Full name<input name="full_name" placeholder="Faculty name" required></label><label>Password<input name="password" value="Faculty@123" required></label><button class="primary" type="submit">Add faculty +</button></form>
    </div>
    <div class="panel section-gap"><div class="panel-head"><div><h3>Add subject / class</h3><p>Assign a subject to a faculty member and class group.</p></div></div>
      <form id="subjectForm" class="form-grid"><label>Subject code<input name="code" placeholder="AIML301" required></label><label>Subject name<input name="name" placeholder="Machine Learning" required></label><label>Branch<select name="branch">${["CSE","CSE (AI & ML)","ECE","Civil","Mechanical"].map(x=>`<option>${x}</option>`).join("")}</select></label><label>Year<select name="year">${["1st Year","2nd Year","3rd Year","4th Year"].map(x=>`<option>${x}</option>`).join("")}</select></label><label>Section<input name="section" value="A" required></label><label>Faculty<select name="faculty_id"><option value="">Unassigned</option>${d.faculty.map(f=>`<option value="${f.id}">${esc(f.full_name)} (${esc(f.username)})</option>`).join("")}</select></label><button class="primary" type="submit">Add subject +</button></form>
    </div>
    <div class="panel section-gap"><div class="panel-head"><div><h3>Registered students</h3><p>${d.students.length} demo / registered student accounts</p></div></div>${d.students.length?`<div class="table-wrap"><table><thead><tr><th>Roll number</th><th>Name</th><th>Branch</th><th>Year</th><th>Section</th></tr></thead><tbody>${d.students.map(s=>`<tr><td class="roll">${esc(s.roll_no)}</td><td>${esc(s.full_name)}</td><td>${esc(s.branch)}</td><td>${esc(s.year)}</td><td>${esc(s.section)}</td></tr>`).join("")}</tbody></table></div>`:'<p class="muted">No students found.</p>'}</div>`;
  $("#studentForm").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));try{await api("/api/admin/students",{method:"POST",body:JSON.stringify(data)});toast("Student account created.");renderManage()}catch(err){toast(err.message)}};
  $("#facultyForm").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));try{await api("/api/admin/faculty",{method:"POST",body:JSON.stringify(data)});toast("Faculty account created.");renderManage()}catch(err){toast(err.message)}};
  $("#subjectForm").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.faculty_id=data.faculty_id?Number(data.faculty_id):null;try{await api("/api/admin/subjects",{method:"POST",body:JSON.stringify(data)});subjects=[];toast("Subject added successfully.");renderManage()}catch(err){toast(err.message)}};
}
boot();
