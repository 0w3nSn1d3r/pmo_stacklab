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
        this.method = 'post';
        this.action = '' // Flask compile_data endpoint
        this.operators = subproc['operators'];

        const fieldset = document.createElement('fieldset');
        const legend = document.createElement('legend');
        const title = document.createTextNode(`Select ${this.name}`);
        const submit_button = document.createElement(button);
        submit_button.type = 'submit';

        legend.appendChild(title);
        fieldset.appendChild(legend);
        this.appendChild(fieldset);
        this.appendChild(submit_button);
    }
}

customElements.define('config-menu', ConfigMenu, { extends: 'form' })