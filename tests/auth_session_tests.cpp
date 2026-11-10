#include "../auth/application/AuthCommandService.h"
#include <stdexcept>
#include <vector>
#include <iostream>
using namespace mirage;
using namespace mirage::auth;
void require(bool value) { if(!value) throw std::runtime_error("Auth session assertion failed"); }
class Provider final:public IdentityProvider {
public:
    mutable std::vector<IdentityOperation> calls;
    mutable Json::Value lastPayload;
    int identityStatus=200,passwordStatus=200,revokeStatus=200;
    void execute(IdentityOperation operation,Json::Value payload,std::string,Completion done) const override {
        calls.push_back(operation);lastPayload=std::move(payload);
        int status=operation==IdentityOperation::GetUser?identityStatus:
            operation==IdentityOperation::ResetPassword?passwordStatus:
            operation==IdentityOperation::RevokeAllSessions?revokeStatus:200;
        done(status==200?ApiResult{200,Json::Value(Json::objectValue)}:failure(status,"rejected"));
    }
};
int main() {
    Provider provider;
    AuthCommandService service(provider);
    service.handle(ResendVerificationCommand{"user@example.com"},[](ApiResult result){require(result.status==200);});
    require(provider.lastPayload["type"].asString()=="signup");
    service.handle(VerifyEmailCommand{"user@example.com","12345678","recovery"},[](ApiResult result){require(result.status==200);});
    require(provider.lastPayload["type"].asString()=="recovery");
    provider.calls.clear();provider.identityStatus=401;
    service.handle(ResetPasswordCommand{"Bearer expired","password"},[](ApiResult result){require(result.status==401);});
    require(provider.calls.size()==1 && provider.calls[0]==IdentityOperation::GetUser);
    provider.calls.clear();
    service.handle(LogoutCommand{"Bearer expired"},[](ApiResult result){require(result.status==401);});
    require(provider.calls.size()==1);
    provider.calls.clear();provider.identityStatus=200;
    service.handle(ResetPasswordCommand{"Bearer valid","password"},[](ApiResult result){require(result.status==200 && result.body["reauthentication_required"].asBool());});
    require(provider.calls==std::vector<IdentityOperation>{IdentityOperation::GetUser,IdentityOperation::ResetPassword,IdentityOperation::RevokeAllSessions});
    provider.calls.clear();provider.passwordStatus=400;
    service.handle(ResetPasswordCommand{"Bearer valid","password"},[](ApiResult result){require(result.status==400);});
    require(provider.calls.size()==2);
    provider.passwordStatus=200;provider.revokeStatus=502;
    service.handle(ResetPasswordCommand{"Bearer valid","password"},[](ApiResult result){require(result.status==503 && result.body["error"].asString()=="password_changed_session_revocation_failed");});
    std::cout<<"PASS: verification payloads, active-session guards, password reset global revocation, partial failure\n";
}
