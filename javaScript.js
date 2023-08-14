var hour = document.getElementById("hour");
var minute = document.getElementById("minute");
var second = document.getElementById("second");
var display = document.getElementById("display");

const audio = new Audio("media/media_audio.mp3");
audio.play();

audio.loop = true;

const add_BTN = document.getElementById("add_alarm");
const alarmlist = document.querySelector(".list");
const input = document.getElementById("timeInput");
const notify = document.querySelector(".alarm_on_off")

//************** DISPLAY TIME and CHECK FOR ALARM TIME *********************

var setTime = () => {

    var d = new Date();
    h = d.getHours();
    m = d.getMinutes();
    s = d.getSeconds();
    // here matching, if any alarm time is matching with current time or not?
    for (let i = 0; i < localStorage.length; i++) {

        var pass = localStorage.getItem(localStorage.key(i));
        if (pass !== 'W' && pass !== 'F') {  // localStorage is storing data for IMDb also;

            var alarm_object = JSON.parse(pass);
            var formatTime = alarm_object.time.split(":"); //converting to array of hour / minute / second

            if ((formatTime[0] == h && formatTime[1] == m && formatTime[2] == s) && !alarm_object.completed) {
                audio.play();
                notify.classList.toggle("off");
                notify.innerHTML = `Its <b>${h == 12 ? 12 : h % 12} : ${m} : ${s} ${h >= 12 ? "PM" : "AM"}</b> go back to work. <br><span>Hit me to turn off Alarm</span>`;
                toggleBell_localStorage(localStorage.key(i));  //(line-n0-76)
            }
        }
    }
    // here updating time in display
    display.innerHTML = ` ${h == 12 ? 12 : h % 12} : ${m} : ${s} ${h >= 12 ? "PM" : "AM"}`
    hour.style.transform = `rotate(${(h == 12 ? 12 : h % 12) * 30 + Math.floor(m / 16) * 6}deg)`;
    minute.style.transform = `rotate(${m * 6}deg)`;
    second.style.transform = `rotate(${s * 6}deg)`;
}
//************ add alarm to unorderedList****************************
function addToAlarmArray(task) {

    const list = document.createElement("li");
    var temp = task.time.split(":"); //convert time to an array

    list.innerHTML = ` 
    <label for="">${(temp[0] == 12 || temp[0] == 0) ? 12 : temp[0] % 12} : ${temp[1]} : ${temp[2]} ${temp[0] >= 12 ? "PM" : "AM"}</label>  
    <i class="bi bi-bell-fill toggle" data-id="${task.time}"></i>
    <i class="bi bi-bell-slash-fill toggle off" data-id="${task.time}"></i>
    <i class="bi bi-trash delete" data-id="${task.time}"></i>
    `    ;
    alarmlist.append(list);

    if (task.completed) {  // since this function is also called from renderList function ,(it can be a completed alarm) 
        toggleBell_icon(task.time); // (line no- 62)
    }
}

//**************** Toggle bell Icon ************************************
function toggleBell_icon(pass) {

    var bell = document.querySelectorAll(".bi-bell-fill");
    var bell_Off = document.querySelectorAll(".bi-bell-slash-fill");

    for (let i = 0; i < bell.length; i++) {
        if (bell[i].dataset.id == pass) {
            bell[i].classList.toggle("off");
            bell_Off[i].classList.toggle("off");
        }
    }
}

//*********************toggle bell inside local storage*******************
function toggleBell_localStorage(KEY) {

    let currentTask = JSON.parse(localStorage.getItem(KEY));  // custom function returns object (line No-  122)
    currentTask.completed = !currentTask.completed;

    localStorage.setItem(KEY, JSON.stringify(currentTask));//toggle hoke store ho jaega
    toggleBell_icon(KEY);                                       //(line-no-62)
}

//********************* Render List **********************************
function renderList() {
    alarmlist.innerHTML = '';
    for (let i = 0; i < localStorage.length; i++) {
        var pass = localStorage.getItem(localStorage.key(i));
        if (pass !== 'W' && pass !== 'F') {  // localStorage is storing data for IMDb also;
            addToAlarmArray(JSON.parse(pass));  //(line-no-43) 
        }
    }
}
//********************** handle delete and on/off *************
function handleClickListener(event) {
    const target = event.target;

    if (target.classList.contains('delete')) {
        localStorage.removeItem(target.dataset.id);
        console.log("Alarm Has Been Successfully Deleted");
        renderList();                                         //(line-no-86)
        return;

    } else if (target.classList.contains('toggle')) {
        toggleBell_localStorage(target.dataset.id);
        console.log("Alarm Has Been Toggled Successfully");
        return;
    }
}

//**************** Check is alarm already exist ??? *********************
function check_validity(task) {

    if (localStorage.getItem(task.time) == null) {
        localStorage.setItem(task.time, JSON.stringify(task));
        addToAlarmArray(task);                                      //(line-no-43)
        console.log("Alarm Has Been Added Successfully ");
    } else {
        console.log("Alarm Already Exist")
    }
}

//*****************add Alarm Helper Function******************************
function addAlarmHelperFunction() {

    const task = {
        time: input.value,
        completed: false,
    };
    check_validity(task);               // (line-no-57)
    input.value = "00:00:00";
}

//************** add new alarm both the function *************
function addBtnFunction(event) {
    event.preventDefault();
    addAlarmHelperFunction();           //(line-no-124)
}
function handleInputKeypress(e) {
    if (e.key === "Enter")
        addAlarmHelperFunction();       //(line-no-124)
}

//**************EVeNT LISTENER***************************************
add_BTN.addEventListener('click', addBtnFunction); //add alarm using plus icon        (line-no-135)
input.addEventListener("keyup", handleInputKeypress);//add alarm  using enter key     (line-no-139)
document.addEventListener('click', handleClickListener);

//****************** Alarm off btn ********************************
notify.addEventListener('click', () => {
    notify.classList.toggle('off');
    notify.innerHTML = '';
    audio.pause();
})

// initialising previous saved alarm time*****************************
function initialising() {
    let n = localStorage.length;
    for (let i = n - 1; i >= 0; i--) {
        var pass = localStorage.getItem(localStorage.key(i));
        if (pass !== 'W' && pass !== 'F') {
            addToAlarmArray(JSON.parse(pass));
        } //(line-no-43)
    }
}

initialising();//(line-no-157)

// now timer***********************************************************
setInterval(() => {
    setTime();                                  //(line-no-16)
}, 1000);

//since setInterval start after 1s
setTime();                                      //(line-no-16)