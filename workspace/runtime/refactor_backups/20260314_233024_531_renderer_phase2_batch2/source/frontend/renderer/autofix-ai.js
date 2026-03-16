export function createAutofixAiController({ helpers }) {
    return {
        showDetail(violation, eventName, options = {}) {
            return helpers.showDetailInternal(violation, eventName, options);
        },
    };
}
