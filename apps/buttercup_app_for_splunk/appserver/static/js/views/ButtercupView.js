require.config({
    paths: {
        text: "../app/" + splunkjs.mvc.Components.getInstance("env").toJSON().app + "/contrib/text"
    }
});


define([
    "underscore",
    "backbone",
    "splunkjs/mvc",
    "jquery",
    "splunkjs/mvc/simplesplunkview",
    "splunkjs/mvc/searchmanager",
    'text!../app/' + splunkjs.mvc.Components.getInstance("env").toJSON().app + '/js/templates/ButtercupJSView.html',
    "css!../app/" + splunkjs.mvc.Components.getInstance("env").toJSON().app + "/css/ButtercupJSView.css"
], function (
    _,
    Backbone,
    mvc,
    $,
    SimpleSplunkView,
    SearchManager,
    Template
) {
        // Define the custom view class
        var ButtercupView = SimpleSplunkView.extend({
            className: "ButtercupView",

            events: {
                "click .get-most-recent-event": "doGetMostRecentEvent"
            },

            defaults: {

            },

            initialize: function () {
                this.options = _.extend({}, this.defaults, this.options);

                //this.some_option = this.options.some_option;
            },


            doGetMostRecentEvent: function () {

                // Make a search
                var search = new SearchManager({
                    "id": "get-most-recent-event-search",
                    "earliest_time": "-1h@h",
                    "latest_time": "now",
                    "search": 'index=_internal OR index=main | head 1 | fields _raw',
                    "cancelOnUnload": true,
                    "autostart": false,
                    "auto_cancel": 90,
                    "preview": false
                }, { tokens: true });


                search.on('search:failed', function () {
                    alert("Search failed");
                }.bind(this));

                search.on("search:start", function () {
                    console.log("Search started");
                }.bind(this));

                search.on("search:done", function () {
                    console.log("Search completed");
                }.bind(this));

                // Get a reference to the search results
                var searchResults = search.data("results");

                // Process the results of the search when they become available
                searchResults.on("data", function () {
                    $("#most-recent-event", this.$el).val(searchResults.data().rows[0][0]);
                }.bind(this));

                // Start the search
                search.startSearch();

            },

            render: function () {

                this.$el.html(_.template(Template, {
                    //'some_option' : some_option
                }));

            }
        });

        return ButtercupView;
    });