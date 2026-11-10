#include "AccountService.h"
namespace mirage::auth
{
namespace
{
std::string displayName(const Json::Value &user)
{
    const auto &metadata = user["user_metadata"];
    if (!metadata.isObject())
        return "Usuario Mirage";
    for (const auto *key : {"display_name", "full_name", "name"})
    {
        const auto &value = metadata[key];
        if (value.isString())
        {
            const auto name = value.asString();
            if (!name.empty() && name.size() <= 100 && name.find('\0') == std::string::npos &&
                name.find_first_not_of(" \t\r\n") != std::string::npos)
                return name;
        }
    }
    return "Usuario Mirage";
}
} // namespace
void AccountService::handle(const RegisterUserCommand &command, Completion done) const
{
    commands_.handle(command, sessionCompletion(std::move(done), true));
}
void AccountService::handle(const LoginCommand &command, Completion done) const
{
    commands_.handle(command, sessionCompletion(std::move(done)));
}
void AccountService::handle(const GoogleSignInCommand &command, Completion done) const
{
    commands_.handle(command, sessionCompletion(std::move(done)));
}
void AccountService::handle(const VerifyEmailCommand &command, Completion done) const
{
    commands_.handle(command, sessionCompletion(std::move(done)));
}
Completion AccountService::sessionCompletion(Completion done, bool allowPendingConfirmation) const
{
    return [this, done = std::move(done), allowPendingConfirmation](ApiResult result) {
        if (result.status != 200)
        {
            done(std::move(result));
            return;
        }
        if (!result.body.isObject())
        {
            done(failure(502, "invalid_provider_session"));
            return;
        }
        if (!result.body["access_token"].isString() ||
            result.body["access_token"].asString().empty())
        {
            if (allowPendingConfirmation)
            {
                result.body["profile_ready"] = false;
                done(std::move(result));
            }
            else
                done(failure(502, "invalid_provider_session"));
            return;
        }
        ensureProfile(std::move(result), std::move(done));
    };
}
void AccountService::rejectSession(const std::string &bearer, Completion done) const
{
    // Revoke the undelivered refresh session if profile initialization failed.
    commands_.handle(LogoutCommand{bearer}, [done = std::move(done)](ApiResult) {
        done(failure(503, "profile_initialization_failed"));
    });
}
void AccountService::ensureProfile(ApiResult session, Completion done) const
{
    const auto &user = session.body["user"];
    const auto bearer = "Bearer " + session.body["access_token"].asString();
    if (!user.isObject() || !user["id"].isString())
    {
        rejectSession(bearer, std::move(done));
        return;
    }
    profile::ProfileAccess access{user["id"].asString(), bearer};
    profileQueries_.handle(
        profile::GetProfileQuery{access},
        [this, access, session = std::move(session),
         done = std::move(done)](profile::ProfileResult result) mutable {
            if (result.aggregate)
            {
                session.body["profile_ready"] = true;
                done(std::move(session));
                return;
            }
            if (result.status != 404)
            {
                rejectSession(access.bearer, std::move(done));
                return;
            }
            profile::UserProfile userProfile{newProfileId_(),
                                             access.userId,
                                             displayName(session.body["user"]),
                                             {},
                                             {},
                                             {},
                                             "",
                                             ""};
            profileCommands_.handle(
                profile::CreateProfileCommand{access, std::move(userProfile)},
                [this, access, session = std::move(session),
                 done = std::move(done)](profile::ProfileResult created) mutable {
                    if (created.aggregate)
                    {
                        session.body["profile_ready"] = true;
                        done(std::move(session));
                        return;
                    }
                    if (created.status != 409)
                    {
                        rejectSession(access.bearer, std::move(done));
                        return;
                    }
                    // A concurrent sign-in may have created the same account's profile.
                    profileQueries_.handle(
                        profile::GetProfileQuery{access},
                        [this, access, session = std::move(session),
                         done = std::move(done)](profile::ProfileResult existing) mutable {
                            if (!existing.aggregate)
                            {
                                rejectSession(access.bearer, std::move(done));
                                return;
                            }
                            session.body["profile_ready"] = true;
                            done(std::move(session));
                        });
                });
        });
}
} // namespace mirage::auth
