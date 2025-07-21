import sys
import os

# Adaugam calea catre folderul python_calculator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "python_calculator")))

from python_calculator.calculator import process_expression

from flask import Flask, render_template_string, request, session

app = Flask(__name__)

# ----------------------------- HTML TEMPLATE ----------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
        }
        .window {
            position: absolute;
            left: {{ x }}px;
            top: {{ y }}px;
            width: {{ w }}px;
            height: {{ h }}px;
            border: 2px solid #333;
            background-color: #ccc;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
            padding: 10px;
        }
        .display-container {
            position: absolute;
            top: 50px;
            left: 100px;
            display: flex;
            align-items: center;
        }
        .display-label {
            font-family: sans-serif;
            font-size: 14px;
            margin-right: 10px;
        }
        .display-box {
            width: 200px;
            height: 50px;
            border: 1px solid #666;
            background-color: #fff;
            font-family: monospace;
            font-size: 14px;
            padding: 5px;
            box-sizing: border-box;
        }
        .radio-button {
            position: absolute;
            top: 120px;
            left: 100px;
            font-family: sans-serif;
            font-size: 14px;
        }
        .return-button {
            position: absolute;
            left: {{ ret_x }}px;
            top: {{ ret_y }}px;
            width: {{ ret_w }}px;
            height: {{ ret_h }}px;
            font-size: 12px;
        }
        .radio-group {
            position: absolute;
            top: 150px;
            left: 160px;
            width: 200px;
            border: 1px solid #333;
            background-color: #eee;
            padding: 10px;
        }
    </style>
</head>
<body>
    <div class="window">
        <div class="display-container">
            <div class="display-label">calculator function</div>
            <input class="display-box" type="text" value="{{ first_text }}" readonly>

            <div class="display-label" style="margin-left: 20px;">n-th fibbonaci number</div>
            <input class="display-box" type="text" value="{{ second_text }}" readonly>

            <div class="display-label" style="margin-left: 20px;">factorial of the number</div>
            <input class="display-box" type="text" value="{{ third_text }}" readonly>
        </div>
        
        <form method="post">
            <div class="radio-group">
                {% set custom_labels = ["calculator function", "n-th fibbonaci number", "factorial of the number"] %}
                {% for i in range(radio_buttons | length) %}
                <div class="radio-option">
                    <input type="radio" id="{{ radio_buttons[i].id }}" name="radio_option" value="{{ i + 1 }}" 
                        {% if selected_choice == i + 1 %}checked{% endif %}>
                    <label for="{{ radio_buttons[i].id }}">{{ custom_labels[i] }}</label>
                </div>
                {% endfor %}
            </div>
            
            <div style="position: absolute; top: 130px; left: 400px;">
                <label for="edit_box" style="font-family: sans-serif; font-size: 14px;">My Input</label><br>
                <textarea id="edit_box" name="edit_box" style="width: 150px; height: 100px; font-family: monospace; font-size: 14px;">{{ current_input }}</textarea>
            </div>
            
            <button class="return-button" type="submit">&Return</button>
        </form>
    </div>
</body>
</html>
"""

# ----------------------------- CLASSES ---------------------------------------

class Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def getX(self):
        return self._x

    def getY(self):
        return self._y
    
    def setY(self, y):
        self._y = y

class Fl_Output:
    def __init__(self, x, y, w, h, label=None):
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.label = label
        self._value = ""

    def value(self, txt):
        self._value = txt

    def redraw(self):
        pass

    def getText(self):
        return self._value

class MyDisplayBox(Fl_Output):
    def __init__(self, pos: Point, w: int, h: int, label: str = None):
        super().__init__(pos.getX(), pos.getY(), w, h, label)

    def setText(self, txt: str):
        self.value(txt)
        self.redraw()

class MyReturnButton:
    def __init__(self, pos: Point, w: int, h: int, label: str = "&Return"):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = label
        self.tooltip = "Push Return button to exit"
        self.labelsize = 12

    def getRenderParams(self):
        return {
            "ret_x": self.x,
            "ret_y": self.y,
            "ret_w": self.w,
            "ret_h": self.h,
            "label": self.label
        }

# ----------------------------- EDIT BOX CLASS ----------------------------------

class MyEditBox:
    def __init__(self, pos: Point, w: int, h: int, label: str):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = label
        self.tooltip = "Input field for short text with newlines."
        self.wrap = True  # Equivalent behavior
        self.controller = None
        self.value = ""

    def setText(self, txt: str):
        self.value = txt

    def getText(self):
        return self.value

    def input_cb(self):
        # Placeholder for future callback logic, e.g., notify controller or update model
        pass

    def getRenderParams(self):
        return {
            "edit_x": self.x,
            "edit_y": self.y,
            "edit_w": self.w,
            "edit_h": self.h,
            "edit_label": self.label,
            "edit_value": self.value
        }
        
# ----------------------------- MODEL CLASS ------------------------------------

class Model:
    def __init__(self):
        self.lastChoice = 0
        self.lastInput = ""
        self.chView = None
        self.inpView = None
        self.factorialOutputView = None

    def setLastChoice(self, ch):
        self.lastChoice = ch
        self.notify()

    def getLastChoice(self):
        return self.lastChoice

    def setCalculatorView(self, db: MyDisplayBox):
        self.calculatorOutputView = db

    def setFibonacciView(self, db: MyDisplayBox):
        self.fibonacciOutputView = db
    
    def setLastInput(self, txt):
        self.lastInput = txt

    def setFactorialView(self, db: MyDisplayBox):
        self.factorialOutputView = db

    def notify(self):
        if self.calculatorOutputView:
            self.calculatorOutputView.setText("Last choice is " + str(self.lastChoice))
        if self.fibonacciOutputView:
            self.fibonacciOutputView.setText(f"Last input is `{self.lastInput}`")

# ----------------------------- CONTROLLER CLASS -------------------------------

class Controller:
    def __init__(self):
        self.model = None

    def setModel(self, aModel: Model):
        self.model = aModel

    def chControl(self, aString: str): # apply the action from the GUI to the model
        try:
            ch = int(aString.strip().split()[-1])
            self.model.setLastChoice(ch)
        except Exception as e:
            print("Invalid input to Controller.chControl:", aString, e)
            
    def inpControl(self, aString: str): # apply the action from the GUI to the model
        self.model.setLastInput(aString)
        
        #Compute based on choice and update view accordingly
        if self.model.getLastChoice() == 1:  # check if the option corresponds to the calculator number option
            try:
                n = aString.strip()
                result = process_expression(n)
                self.model.calculatorOutputView.setText(str(result))
            except Exception as e:
                self.model.calculatorOutputView.setText("Invalid expression")

        if self.model.getLastChoice() == 2: # check if the option corresponds to the n-th fibonacci number option
            try:
                n = int(aString.strip())
                fib = self.fibonnaci(n)
                self.model.fibonacciOutputView.setText(str(fib))
            except Exception as e:
                self.model.fibonacciOutputView.setText("Invalid input")
                
        elif self.model.getLastChoice() == 3: # check if the option corresponds to factorial
            try:
                n = int(aString.strip())
                factorial_result = self.factorial(n)
                self.model.factorialOutputView.setText(str(factorial_result))
            except Exception as e:
                self.model.factorialOutputView.setText("Invalid input")
    
    def fibonnaci(self, n):
        #base condition
        if(n <= 1):
            return n
        
        #problem broken down into 2 function calls
        #and their results combined and returned
        last = self.fibonnaci(n - 1)
        slast = self.fibonnaci(n - 2)
        
        return last + slast

    def factorial(self, n):  # the function for factorial
        if n < 0:
            return "Error: negative number"
        P = 1
        for i in range(1, n + 1):
            P *= i
        return P

# ----------------------------- VIEW-CONTROLLER ASSOCIATION --------------------

class MyRadioButton:
    _id_counter = 0

    def __init__(self, pos: Point, w: int, h: int, slabel: str):
        self.x = pos.getX()
        self.y = pos.getY()
        self.w = w
        self.h = h
        self.label = slabel
        self.tooltip = "Radio button, only one button is set at a time."
        self.down_box = "FL_ROUND_DOWN_BOX"
        self.id = f"radio{MyRadioButton._id_counter}"
        MyRadioButton._id_counter += 1
        self.controller = None

    def getRenderParams(self):
        return {
            "id": self.id,
            "label": self.label
        }

    def setController(self, aCntrl):
        self.controller = aCntrl

    def radio_button_cb(self):
        if self.controller:
            self.controller.chControl(self.label)

class MyRadioGroup:
    def __init__(self, pos: Point, w: int, h: int, label: str, no: int):
        self.elts = []
        bpos = Point(pos.getX(), pos.getY())
        for i in range(no):
            bpos.setY(pos.getY() + i * 30)
            rb = MyRadioButton(bpos, w, h // no, f"My Choice {i + 1}")
            self.elts.append(rb)

    def getButtons(self):
        return self.elts
    
    def setController(self, aCntrl):
        for rb in self.elts:
            rb.setController(aCntrl)

# ----------------------------- CONNECTION LOGIC ----------------------------------------

class MyWindow:
    def __init__(self, pos: Point, w: int, h: int, title: str):
        if pos is None:
            self.x, self.y = 100, 200
        else:
            self.x, self.y = pos.getX(), pos.getY()
        self.w = w
        self.h = h
        self.title = title
        self.display_box = None
        self.return_button = None
        self.radio_buttons = []
        
        # Store references to all three display boxes
        self.firstdb = None
        self.seconddb = None
        self.thirddb = None

    def addDisplayBox(self, display_box: MyDisplayBox):
        if self.firstdb is None:
            self.firstdb = display_box
        elif self.seconddb is None:
            self.seconddb = display_box
        elif self.thirddb is None:
            self.thirddb = display_box

    def addReturnButton(self, return_button: MyReturnButton):
        self.return_button = return_button
        
    def addRadioButton(self, rb: MyRadioButton):
        self.radio_buttons.append(rb)
    
    def addRadioGroup(self, group):
        self.radio_buttons.extend(group.getButtons())

    def getRenderParams(self):
        params = {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "title": self.title,
            "first_display_box_text": self.firstdb.getText() if self.firstdb else "",
            "second_display_box_text": self.seconddb.getText() if self.seconddb else "",
            "third_display_box_text": self.thirddb.getText() if self.thirddb else "",
            "label": self.display_box.label if self.display_box else ""
        }
        if self.return_button:
            params.update(self.return_button.getRenderParams())
        if self.radio_buttons:
            params["radio_buttons"] = [rb.getRenderParams() for rb in self.radio_buttons]
        return params

# ----------------------------- ROUTING --------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    posMainWindow = Point(100, 200)
    mainwindow = MyWindow(posMainWindow, 950, 400, "Main Window")

    # Display Boxes
    posFirstDB = Point(100, 50)
    firstdb = MyDisplayBox(posFirstDB, 200, 50, "My display box")

    posSndDB = Point(375, 50)
    seconddb = MyDisplayBox(posSndDB, 200, 50, "Second display")

    posTrdDB = Point(200, 275)
    thirddb = MyDisplayBox(posTrdDB, 250, 50, "Third display")

    firstdb.setText("My first output text.")
    seconddb.setText("My second output text.")
    thirddb.setText("My third output text.")

    mainwindow.addDisplayBox(firstdb)
    mainwindow.addDisplayBox(seconddb)
    mainwindow.addDisplayBox(thirddb)

    # Model and Controller
    model = Model()
    model.setCalculatorView(firstdb) # set the calculator view to the first display box
    model.setFibonacciView(seconddb) # set the fibonacci view to the second display box
    model.setFactorialView(thirddb)  # set the factorial view to the third display box

    chCntrl = Controller()
    chCntrl.setModel(model)

    # Radio Group
    posRG = Point(160, 150)
    rg = MyRadioGroup(posRG, 150, 90, "MyChoice", 3)
    rg.setController(chCntrl)
    mainwindow.addRadioGroup(rg)

    # Return Button
    posRet = Point(400, 350)
    ret = MyReturnButton(posRet, 100, 25)
    mainwindow.addReturnButton(ret)

    # Edit Box input
    posEB = Point(400, 130)
    eb = MyEditBox(posEB, 150, 100, "&My Input")
    eb.setText("Initial edit text\nSecond line")

    if request.method == "POST":
        input_text = request.form.get("edit_box", "")
        selected_choice = request.form.get("radio_option", "") # processing the value of the selected radio button
        
        # Process radio button selection
        if selected_choice:
            chCntrl.chControl(selected_choice)
        
        # Process input text
        chCntrl.inpControl(input_text)
        
        # Set current_input for rendering
        current_input = input_text
        eb.setText(input_text)
    else:
        # For GET requests, use the initial text
        current_input = eb.getText()
        selected_choice = ""
    
    # Prepare render parameters
    render_params = mainwindow.getRenderParams()
    render_params.update({
        "selected_choice": int(selected_choice) if selected_choice else 0,
        "current_input": current_input,
        "first_text": firstdb.getText(),
        "second_text": seconddb.getText(),
        "third_text": thirddb.getText()
    })
    
    return render_template_string(HTML_TEMPLATE, **render_params)
    
if __name__ == "__main__":
    app.run(debug=True)