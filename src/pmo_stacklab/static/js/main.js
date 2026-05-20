const { createElement } = require("react");

// Algorithm configuration object (used as radio options for ConfigMenu)
class AlgoItem extends HTMLListElement {
    constructor() {
        super();
    }
}


/** 
 * Configuration menu element for subprocesses;
 * Takes JSON formatted instances of the Subprocess
 * class to dynamically load the appropriate input
 * fields on app startup, thus enabling the addition
 * of new subprocess algorithm options without the need
 * to manually reconfigure the corresponding input interface.
 * 
 * @param {Subprocess} subproc - The instance of the Subprocess class
                                * corresponding to the desired input interface, 
                                * such that the instance ConfigMenu(subproc)
                                * is an element allowing the user to configure
                                * all parameters through the GUI, 
                                * including the arguments of algorithm options.
 */
class ConfigMenu extends HTMLFormElement {
    constructor(subproc) {
        super();
        this.name = subproc['name'];
        this.operators = subproc['operators'];

        // Create the menu title
        const fieldset = document.createElement('fieldset');
        const legend = document.createElement('legend');
        const title = document.createTextNode(`Select ${this.name}`);

        legend.appendChild(title);
        fieldset.appendChild(legend);

        // Create the submit button
        const submit_button = document.createElement(button);
        submit_button.type = 'submit';
    }
}