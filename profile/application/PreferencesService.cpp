#include "PreferencesService.h"
namespace mirage::profile
{
void PreferencesCommandService::handle(const UpdatePreferencesCommand &command,
                                       ProfileCompletion done) const
{
    repository_.findByUserId(
        command.access, [this, command, done = std::move(done)](ProfileResult result) {
            if (!result.aggregate)
            {
                done(std::move(result));
                return;
            }
            try
            {
                result.aggregate->updatePreferences(command.preferences);
            }
            catch (const std::invalid_argument &e)
            {
                done({400, {}, e.what()});
                return;
            }
            repository_.updatePreferences(command.access, result.aggregate->preferences(),
                                          std::move(done));
        });
}

} // namespace mirage::profile
